"""
台灣房價查詢 Web API — FastAPI
端點：
  GET /api/query          - 近期成交案例
  GET /api/district-stats - 行政區統計
  GET /api/compare        - 比較兩行政區
  GET /api/trend          - 房價趨勢
  GET /api/community      - 社區名稱搜尋
  GET /api/export/csv     - 匯出 CSV
"""

import csv
import io
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from geocoding import geocode_address, parse_address
from lvrs import get_district_stats, search_transactions

load_dotenv()

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

app = FastAPI(title="台灣房價查詢 API")


def resolve_address(address: str) -> tuple[str, str]:
    city = district = ""
    if GOOGLE_MAPS_KEY:
        loc = geocode_address(address, GOOGLE_MAPS_KEY)
        if loc:
            return loc.get("city", ""), loc.get("district", "")
    city, district = parse_address(address)
    return city, district


@app.get("/api/query")
def api_query(address: str = Query(..., description="地址或行政區"), limit: int = 15):
    city, district = resolve_address(address)
    if not city:
        raise HTTPException(400, "無法識別縣市，請提供完整地址（含縣市名）")
    rows = search_transactions(city, district=district, limit=limit)
    return {"city": city, "district": district, "count": len(rows), "records": rows}


@app.get("/api/district-stats")
def api_district_stats(address: str = Query(...)):
    city, district = resolve_address(address)
    if not city:
        raise HTTPException(400, "無法識別縣市")
    return get_district_stats(city, district)


@app.get("/api/compare")
def api_compare(address1: str = Query(...), address2: str = Query(...)):
    city1, district1 = resolve_address(address1)
    city2, district2 = resolve_address(address2)
    if not city1 or not city2:
        raise HTTPException(400, "無法識別其中一個縣市")
    return {
        f"{city1}{district1}": get_district_stats(city1, district1),
        f"{city2}{district2}": get_district_stats(city2, district2),
    }


@app.get("/api/community")
def api_community(city: str = Query(...), keyword: str = Query(...), limit: int = 20):
    rows = search_transactions(city, keyword=keyword, limit=limit)
    return {"city": city, "keyword": keyword, "count": len(rows), "records": rows}


@app.get("/api/export/csv")
def api_export_csv(address: str = Query(...), limit: int = 50):
    city, district = resolve_address(address)
    if not city:
        raise HTTPException(400, "無法識別縣市")
    rows = search_transactions(city, district=district, limit=limit)
    if not rows:
        raise HTTPException(404, "查無資料")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    filename = f"{city}{district}_實價登錄.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
