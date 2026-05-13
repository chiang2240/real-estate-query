"""
實價登錄 open data API 整合
資料來源：內政部不動產成交案件實際資訊資料供應系統
API：https://plvr.land.moi.gov.tw/Download?fileName={city}_lvr_land_a.csv
"""

import csv
import io
import json
import time
import requests
import urllib3
from pathlib import Path
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_TTL = 6 * 3600  # 6 小時

CITY_CODES: dict[str, str] = {
    "臺北市": "A", "台北市": "A",
    "臺中市": "B", "台中市": "B",
    "基隆市": "C",
    "臺南市": "D", "台南市": "D",
    "高雄市": "E",
    "新北市": "F",
    "宜蘭縣": "G",
    "桃園市": "H",
    "嘉義市": "I",
    "新竹縣": "J",
    "苗栗縣": "K",
    "南投縣": "M",
    "彰化縣": "N",
    "新竹市": "O",
    "雲林縣": "P",
    "嘉義縣": "Q",
    "屏東縣": "T",
    "花蓮縣": "U",
    "臺東縣": "V", "台東縣": "V",
    "金門縣": "W",
    "澎湖縣": "X",
    "連江縣": "Z",
}

BASE_URL = "https://plvr.land.moi.gov.tw/Download"


def get_city_code(city: str) -> Optional[str]:
    for name, code in CITY_CODES.items():
        if name in city or city in name:
            return code
    return None


def _cache_path(city_code: str, category: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{city_code}_{category}.json"


def fetch_raw_data(city_code: str, category: str = "A") -> list[dict]:
    """下載單一城市的實價登錄買賣資料（CSV），回傳 list[dict]。"""
    cache_file = _cache_path(city_code, category)

    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < CACHE_TTL:
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            print(f"  [快取命中：{city_code}，共 {len(data)} 筆]")
            return data
        except Exception:
            pass

    filename = f"{city_code.lower()}_lvr_land_{category.lower()}.csv"
    try:
        resp = requests.get(BASE_URL, params={"fileName": filename}, timeout=30, verify=False)
        resp.raise_for_status()
        text = resp.content.decode("utf-8-sig")
        lines = text.splitlines()
        # 第 0 行：中文欄位，第 1 行：英文欄位，第 2 行起：資料
        if len(lines) < 3:
            return []
        reader = csv.DictReader(io.StringIO("\n".join([lines[0]] + lines[2:])))
        result = list(reader)
        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"  [API 下載：{city_code}，共 {len(result)} 筆，已快取]")
        return result
    except Exception as e:
        print(f"  [下載失敗：{e}]")
    return []


def _roc_date(date_str: str) -> str:
    s = str(date_str).strip()
    if len(s) == 7 and s.isdigit():
        return f"{int(s[:3]) + 1911}/{s[3:5]}/{s[5:7]}"
    return s


def _to_float(v) -> Optional[float]:
    try:
        return float(v) if v not in (None, "", "null") else None
    except (ValueError, TypeError):
        return None


def format_record(item: dict) -> dict:
    total_price = _to_float(item.get("總價元"))
    area_m2 = _to_float(item.get("建物移轉總面積平方公尺"))
    area_ping = round(area_m2 / 3.30579, 1) if area_m2 else None
    total_wan = round(total_price / 10000) if total_price else None
    unit_price = round(total_wan / area_ping, 1) if (total_wan and area_ping) else None

    rooms = item.get("建物現況格局-房", "")
    halls = item.get("建物現況格局-廳", "")
    baths = item.get("建物現況格局-衛", "")
    layout = f"{rooms}房{halls}廳{baths}衛" if rooms else ""

    return {
        "地址": str(item.get("土地位置建物門牌", "")).strip(),
        "行政區": str(item.get("鄉鎮市區", "")).strip(),
        "交易標的": item.get("交易標的", ""),
        "建物型態": item.get("建物型態", ""),
        "格局": layout,
        "樓層": item.get("移轉層次", ""),
        "總樓層": item.get("總樓層數", ""),
        "建物面積(坪)": area_ping,
        "總價(萬)": total_wan,
        "單價(萬/坪)": unit_price,
        "屋齡建成": item.get("建築完成年月", ""),
        "交易日期": _roc_date(item.get("交易年月日", "")),
    }


def search_transactions(city: str, district: str = "", keyword: str = "", limit: int = 20) -> list[dict]:
    city_code = get_city_code(city)
    if not city_code:
        return []

    raw = fetch_raw_data(city_code)
    results = []
    for item in raw:
        item_district = str(item.get("鄉鎮市區", ""))
        item_addr = str(item.get("土地位置建物門牌", ""))

        if district and district not in item_district:
            continue
        if keyword and keyword not in item_addr and keyword not in item_district:
            continue

        results.append(format_record(item))
        if len(results) >= limit:
            break

    return results


def get_district_stats(city: str, district: str) -> dict:
    transactions = search_transactions(city, district=district, limit=100)

    if not transactions:
        return {"error": f"查無「{city}{district}」的實價登錄資料"}

    unit_prices = [t["單價(萬/坪)"] for t in transactions if t.get("單價(萬/坪)")]
    total_prices = [t["總價(萬)"] for t in transactions if t.get("總價(萬)")]

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    return {
        "城市": city,
        "行政區": district,
        "統計筆數": len(transactions),
        "均價(萬/坪)": avg(unit_prices),
        "最高單價(萬/坪)": round(max(unit_prices), 1) if unit_prices else None,
        "最低單價(萬/坪)": round(min(unit_prices), 1) if unit_prices else None,
        "平均總價(萬)": avg(total_prices),
        "最近成交案例": transactions[:8],
    }
