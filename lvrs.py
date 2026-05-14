"""
實價登錄服務層：對外提供 search_transactions、get_district_stats。
資料存取交由 crawler.LvrsCrawler，模型定義在 models.py。
"""

from typing import Optional

import datetime

from crawler import HistoryCrawler, LvrsCrawler
from models import DistrictStats

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


def get_city_code(city: str) -> Optional[str]:
    for name, code in CITY_CODES.items():
        if name in city or city in name:
            return code
    return None


async def search_transactions(
    city: str, district: str = "", keyword: str = "", limit: int = 20
) -> list[dict]:
    city_code = get_city_code(city)
    if not city_code:
        return []
    crawler = LvrsCrawler(city_code)
    return await crawler.query(district=district, keyword=keyword, limit=limit)


async def get_district_stats(city: str, district: str) -> dict:
    transactions = await search_transactions(city, district=district, limit=100)

    if not transactions:
        return {"error": f"查無「{city}{district}」的實價登錄資料"}

    unit_prices = [t["單價(萬/坪)"] for t in transactions if t.get("單價(萬/坪)")]
    total_prices = [t["總價(萬)"]    for t in transactions if t.get("總價(萬)")]

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    stats = DistrictStats(
        城市=city,
        行政區=district,
        統計筆數=len(transactions),
        均價_萬坪=avg(unit_prices),
        最高單價_萬坪=round(max(unit_prices), 1) if unit_prices else None,
        最低單價_萬坪=round(min(unit_prices), 1) if unit_prices else None,
        平均總價_萬=avg(total_prices),
        最近成交案例=transactions[:8],
    )
    return stats.to_display()


def _build_seasons(years: int) -> list[str]:
    roc_now = datetime.date.today().year - 1911
    seasons = []
    for y in range(roc_now - years + 1, roc_now + 1):
        for s in range(1, 5):
            token = f"{y:03d}S{s}"
            if token >= "101S1":
                seasons.append(token)
    return seasons


async def get_price_trend(
    city: str, district: str = "", keyword: str = "", years: int = 10
) -> dict:
    city_code = get_city_code(city)
    if not city_code:
        return {"error": f"無法識別縣市：{city}"}

    seasons = _build_seasons(years)
    crawler = HistoryCrawler(city_code)
    trend = await crawler.get_trend(seasons, district=district, keyword=keyword)

    return {
        "城市": city,
        "行政區": district or "（全區）",
        "關鍵字": keyword or "",
        "查詢季別數": len(seasons),
        "有資料季別數": len(trend),
        "趨勢數據": trend,
    }
