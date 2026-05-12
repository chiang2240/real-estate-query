"""
591 實價登錄爬蟲

抓取指定社區的成交紀錄，回傳 list[dict]，
每個 dict 對應 data/transactions.csv 的一列。
"""

import re
import time
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

_PRICE_URL = "https://market.591.com.tw/{community_id}/price"


def fetch(building_id: int, source_591_id: int, max_records: int = 30) -> list[dict]:
    """
    抓取 591 社區成交紀錄。

    Args:
        building_id:   對應 buildings.csv 的 id，寫入結果欄位用。
        source_591_id: 591 的社區編號（URL 上的數字）。
        max_records:   最多回傳幾筆（預設 30）。

    Returns:
        list of dict，符合 transactions.csv schema。
        若抓取失敗回傳空 list。
    """
    url = _PRICE_URL.format(community_id=source_591_id)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[fetcher_591] 請求失敗 {url}: {e}")
        return []

    time.sleep(1)  # 禮貌性延遲，避免對伺服器造成壓力

    soup = BeautifulSoup(resp.text, "lxml")
    return _parse(soup, building_id, max_records)


def _parse(soup: BeautifulSoup, building_id: int, max_records: int) -> list[dict]:
    records = []

    # 591 成交紀錄表格的 class 可能隨版本異動，以下為當前結構
    rows = soup.select("table.price-table tbody tr, .price-record-item")
    if not rows:
        # fallback: 找所有包含成交日期格式的列
        rows = soup.find_all("tr", attrs={"data-date": True})

    for row in rows[:max_records]:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        texts = [c.get_text(strip=True) for c in cells]
        record = {
            "building_id": building_id,
            "source": "591實價登錄",
            "floor": _clean(texts, 0),
            "date_roc": _clean(texts, 1),
            "date_iso": _roc_to_iso(_clean(texts, 1)),
            "total_price_wan": _clean(texts, 2),
            "unit_price_wan": _clean(texts, 3),
            "size_ping": _clean(texts, 4),
            "layout": _clean(texts, 5),
            "parking": _clean(texts, 6),
        }
        records.append(record)

    return records


def _clean(texts: list[str], idx: int) -> str:
    try:
        return texts[idx].replace(",", "").strip()
    except IndexError:
        return ""


def _roc_to_iso(date_roc: str) -> str:
    """將民國年月（114-12）轉為西元（2025/12）。"""
    m = re.match(r"^(\d{2,3})-(\d{2})$", date_roc)
    if not m:
        return ""
    year = int(m.group(1)) + 1911
    return f"{year}/{m.group(2)}"
