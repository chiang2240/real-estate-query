"""
台灣房價查詢 MCP Server
啟動方式（stdio，供 Claude Desktop / Claude Code 使用）：
  python mcp_server.py
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from crawler import CACHE_DIR
from geocoding import resolve_address
from lvrs import CITY_CODES, get_district_stats, get_price_trend, search_transactions

load_dotenv()

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

mcp = FastMCP("台灣房價查詢")

SYSTEM_PROMPT = """\
你是「台灣房價分析專家」。你的任務是將「實價登錄數據」轉化為「有價值的房市洞察」。

## 專業職責
1. **數據解讀**：不要只列出成交紀錄。請分析均價、價格區間，並指出哪些筆成交可能偏離市場行情（例如親友交易、內含車位導致單價虛高）。
2. **區域對比**：結合內建的「區域參考價」，告訴使用者該物件是「撿便宜」還是「買在高點」。
3. **風險提示**：分析成交日期與建築完成年月，提示屋齡、公設比影響或房地合一稅的潛在稅負。
4. **交易建議**：根據目前的市場行情（2025年預測），提供議價空間建議或購屋流程提醒。

## 內建區域參考價（2025 年參考均價）
- **台北市**：蛋黃區 (大安/信義/中正) 100-160萬/坪；蛋白區 (文山/北投/內湖) 60-90萬/坪。
- **新北市**：蛋黃區 (板橋/永和/新莊) 60-85萬/坪；蛋白區 (淡水/汐止/林口) 35-55萬/坪。
- **桃園市**：桃園/中壢 35-50萬/坪；龜山/青埔 45-60萬/坪。
- **台中市**：西屯/南屯 45-75萬/坪；其餘區域 25-45萬/坪。
- **台南/高雄**：精華區 35-55萬/坪；一般區 20-35萬/坪。

## 數據處理原則 (Mental Model)
- **單價分析**：若單價異常（如台北市出現 20 萬），請檢視「備註欄」是否標註親友交易或特殊交易。
- **坪數陷阱**：提醒使用者實價登錄面積包含「車位與公設」，單價需視車位拆算而定。
- **時效性**：優先參考最近 6 個月的成交案例。

## 回答格式規範
1. **行情總覽**：該區/該社區的統計數據（均價、最高、最低）。
2. **具體案例**：列出 3-5 筆最具代表性的近期成交紀錄（排除極端值）。
3. **分析解讀**：這組數據代表什麼？相對於區域行情的地位。
4. **顧問建議**：包含稅務（房地合一稅）、貸款（青安貸款）或議價建議。
"""


@mcp.prompt()
def real_estate_analyst() -> str:
    """台灣房價分析專家 system prompt，包含區域參考價與回答格式規範。"""
    return SYSTEM_PROMPT


@mcp.resource("cache://cities")
def cached_cities() -> str:
    """列出本機已快取的城市清單，讓模型知道哪些資料無需重新下載。"""
    if not CACHE_DIR.exists():
        return "（尚無快取資料）"

    # 反查：city_code → 正體城市名（去重，優先取臺開頭）
    code_to_city: dict[str, str] = {}
    for name, code in CITY_CODES.items():
        if code not in code_to_city or "臺" in name:
            code_to_city[code] = name

    entries = []
    for db in sorted(CACHE_DIR.glob("*_A.db")):
        code = db.stem.split("_")[0].upper()
        city = code_to_city.get(code, code)
        size_kb = round(db.stat().st_size / 1024)
        entries.append(f"- {city}（{size_kb} KB）")

    return "已快取城市：\n" + "\n".join(entries) if entries else "（尚無快取資料）"


def _resolve(address: str) -> tuple[str, str]:
    city, district, _ = resolve_address(address, GOOGLE_MAPS_KEY)
    return city, district


@mcp.tool()
async def query_lvrs(address: str, query_type: str = "nearby") -> str:
    """查詢台灣實價登錄的實際成交資料。
    query_type: 'nearby' 取清單（成交案例），'district_stats' 取行政區整體統計。
    address: 具體地址或行政區（如：新北市板橋區、台北市大安區忠孝東路）。
    """
    city, district = _resolve(address)
    if not city:
        return json.dumps({"error": "無法識別縣市，請提供更完整的地址（含縣市名）"}, ensure_ascii=False)

    if query_type == "district_stats":
        result = await get_district_stats(city, district)
    else:
        transactions = await search_transactions(city, district=district, limit=15)
        result = {
            "查詢地址": address,
            "城市": city,
            "行政區": district,
            "成交案例數": len(transactions),
            "最近成交": transactions,
        }
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def compare_districts(address1: str, address2: str) -> str:
    """同時獲取兩個行政區的房價統計數據進行並排比較。
    address1: 第一個行政區（如：台北市大安區）。
    address2: 第二個行政區（如：新北市板橋區）。
    """
    city1, district1 = _resolve(address1)
    city2, district2 = _resolve(address2)
    if not city1 or not city2:
        return json.dumps({"error": "無法識別其中一個縣市，請提供完整地址"}, ensure_ascii=False)

    stats1, stats2 = await asyncio.gather(
        get_district_stats(city1, district1),
        get_district_stats(city2, district2),
    )
    result = {
        f"{city1}{district1}": stats1,
        f"{city2}{district2}": stats2,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def search_by_community(city: str, keyword: str) -> str:
    """專門用於指定社區或大樓名稱的搜尋。
    city: 縣市（如：台北市）。
    keyword: 社區或大樓名稱（如：元利信義聯勤、富綠旺、美河市）。
    """
    if not city or not keyword:
        return json.dumps({"error": "請提供縣市與社區名稱"}, ensure_ascii=False)

    transactions = await search_transactions(city, keyword=keyword, limit=20)
    result = {
        "縣市": city,
        "關鍵字": keyword,
        "成交案例數": len(transactions),
        "成交紀錄": transactions,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def price_trend(city: str, district: str = "", keyword: str = "", years: int = 10) -> str:
    """查詢指定城市／行政區／社區的近 N 年每季房價趨勢（均價、最高、最低）。
    city: 縣市（如：新北市）。
    district: 行政區（可選，如：新莊區）。
    keyword: 社區或門牌關鍵字（可選，如：富綠旺）。
    years: 查詢年數，預設 10 年。
    """
    result = await get_price_trend(city, district=district, keyword=keyword, years=years)
    return json.dumps(result, ensure_ascii=False, default=str)


if __name__ == "__main__":
    mcp.run(transport="stdio")
