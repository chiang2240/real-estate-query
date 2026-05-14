import re
from typing import Optional

import httpx


CITY_PATTERN = re.compile(
    r"(台北市|臺北市|新北市|桃園市|台中市|臺中市|台南市|臺南市|高雄市"
    r"|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣"
    r"|嘉義縣|屏東縣|宜蘭縣|花蓮縣|台東縣|臺東縣|澎湖縣|金門縣|連江縣)"
)
DISTRICT_PATTERN = re.compile(r"[一-鿿]{2,4}[區鄉鎮市]")


def geocode_address(address: str, api_key: str) -> Optional[dict]:
    """Convert address to coordinates + city/district via Google Maps."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW", "region": "TW"}

    try:
        resp = httpx.get(url, params=params, timeout=10)
        data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None

        result = data["results"][0]
        loc = result["geometry"]["location"]
        city = district = ""

        for comp in result["address_components"]:
            types = comp["types"]
            name = comp["long_name"]
            if "administrative_area_level_1" in types:
                city = name
            elif "administrative_area_level_2" in types and not district:
                district = name
            elif "sublocality_level_1" in types:
                district = name

        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "city": city,
            "district": district,
            "formatted_address": result["formatted_address"],
        }
    except Exception:
        return None


def parse_address(address: str) -> tuple[str, str]:
    """Fallback: parse city and district from address string."""
    city = m.group(0) if (m := CITY_PATTERN.search(address)) else ""
    district = ""
    for m in DISTRICT_PATTERN.finditer(address):
        candidate = m.group(0)
        if candidate != city:
            district = candidate
            break
    return city, district


def resolve_address(address: str, api_key: str = "") -> tuple[str, str, str]:
    """回傳 (city, district, formatted_address)。優先用 Google Maps，fallback 用 regex。"""
    if api_key:
        loc = geocode_address(address, api_key)
        if loc:
            return loc.get("city", ""), loc.get("district", ""), loc.get("formatted_address", address)
    city, district = parse_address(address)
    return city, district, address
