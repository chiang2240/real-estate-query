"""
LvrsCrawler：負責從內政部實價登錄下載 CSV 並存入 SQLite。
職責邊界：HTTP 下載、CSV 解析、資料清洗、SQLite 讀寫。
"""

import asyncio
import csv
import io
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_TTL = 6 * 3600        # 6 小時：資料快取有效期
CACHE_LIST_TTL = 24 * 3600  # 24 小時：Last-Modified 元資料快取

BASE_URL = "https://plvr.land.moi.gov.tw/Download"

# 排除純土地或純車位，避免拉低建物均價
_EXCLUDE_TYPES = {"土地", "車位"}

# 預設關閉 SSL 驗證（政府網站憑證異常），可透過環境變數啟用
_VERIFY_SSL = os.getenv("LVRS_VERIFY_SSL", "false").lower() == "true"

if not _VERIFY_SSL:
    import warnings
    warnings.warn(
        "LVRS SSL 驗證已關閉 (LVRS_VERIFY_SSL=false)。"
        "生產環境請設定 LVRS_VERIFY_SSL=true。",
        stacklevel=1,
    )


def _db_path(city_code: str, category: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{city_code}_{category}.db"


def _meta_path(city_code: str, category: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{city_code}_{category}_meta.json"


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            district         TEXT,
            address          TEXT,
            transaction_type TEXT,
            building_type    TEXT,
            layout           TEXT,
            floor            TEXT,
            total_floors     TEXT,
            area_ping        REAL,
            total_wan        REAL,
            unit_price       REAL,
            building_year    TEXT,
            transaction_date TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_district ON transactions(district)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_address  ON transactions(address)")
    conn.commit()
    conn.close()


def _db_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    return count


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


def _write_to_db(db_path: Path, rows: list[dict]) -> int:
    _init_db(db_path)
    records = []
    for item in rows:
        transaction_type = str(item.get("交易標的", "")).strip()
        if transaction_type in _EXCLUDE_TYPES:
            continue

        total_price = _to_float(item.get("總價元"))
        area_m2 = _to_float(item.get("建物移轉總面積平方公尺"))
        area_ping = round(area_m2 / 3.30579, 1) if area_m2 else None
        total_wan = round(total_price / 10000) if total_price else None
        unit_price = round(total_wan / area_ping, 1) if (total_wan and area_ping) else None

        rooms = item.get("建物現況格局-房", "")
        halls = item.get("建物現況格局-廳", "")
        baths = item.get("建物現況格局-衛", "")
        layout = f"{rooms}房{halls}廳{baths}衛" if rooms else ""

        records.append((
            str(item.get("鄉鎮市區", "")).strip(),
            str(item.get("土地位置建物門牌", "")).strip(),
            transaction_type,
            item.get("建物型態", ""),
            layout,
            item.get("移轉層次", ""),
            item.get("總樓層數", ""),
            area_ping,
            total_wan,
            unit_price,
            item.get("建築完成年月", ""),
            _roc_date(item.get("交易年月日", "")),
        ))

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM transactions")
    conn.executemany("""
        INSERT INTO transactions
            (district, address, transaction_type, building_type, layout,
             floor, total_floors, area_ping, total_wan, unit_price,
             building_year, transaction_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()
    conn.close()
    return len(records)


def _query_db(db_path: Path, district: str, keyword: str, limit: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    where_clauses: list[str] = []
    params: list = []

    if district:
        where_clauses.append("district LIKE ?")
        params.append(f"%{district}%")
    if keyword:
        where_clauses.append("(address LIKE ? OR district LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM transactions {where} LIMIT ?", params
    ).fetchall()
    conn.close()

    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "地址":        row["address"],
        "行政區":      row["district"],
        "交易標的":    row["transaction_type"],
        "建物型態":    row["building_type"],
        "格局":        row["layout"],
        "樓層":        row["floor"],
        "總樓層":      row["total_floors"],
        "建物面積(坪)": row["area_ping"],
        "總價(萬)":    row["total_wan"],
        "單價(萬/坪)": row["unit_price"],
        "屋齡建成":    row["building_year"],
        "交易日期":    row["transaction_date"],
    }


class LvrsCrawler:
    """實價登錄資料存取層：下載 → 解析 → SQLite。"""

    def __init__(self, city_code: str, category: str = "A"):
        self.city_code = city_code
        self.category = category
        self.db_path = _db_path(city_code, category)
        self.meta_path = _meta_path(city_code, category)
        self._timeout = httpx.Timeout(timeout=None, connect=5.0, read=20.0)

    async def ensure_data(self) -> int:
        """確保本地 SQLite 資料是新鮮的，回傳筆數。"""
        if self.db_path.exists():
            if (time.time() - self.db_path.stat().st_mtime) < CACHE_TTL:
                count = _db_count(self.db_path)
                print(f"  [快取命中：{self.city_code}，共 {count} 筆]")
                return count

        last_modified = self._load_last_modified()
        return await self._download(last_modified)

    def _load_last_modified(self) -> Optional[str]:
        if not self.meta_path.exists():
            return None
        try:
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            if (time.time() - meta.get("checked_at", 0)) < CACHE_LIST_TTL:
                return meta.get("last_modified")
        except Exception:
            pass
        return None

    def _save_meta(self, last_modified: Optional[str]) -> None:
        meta = {"checked_at": time.time(), "last_modified": last_modified}
        self.meta_path.write_text(json.dumps(meta), encoding="utf-8")

    async def _download(self, last_modified: Optional[str]) -> int:
        filename = f"{self.city_code.lower()}_lvr_land_{self.category.lower()}.csv"
        headers: dict[str, str] = {}
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(verify=_VERIFY_SSL, timeout=self._timeout) as client:
                    resp = await client.get(BASE_URL, params={"fileName": filename}, headers=headers)

                self._save_meta(resp.headers.get("last-modified", last_modified))

                if resp.status_code == 304:
                    self.db_path.touch()
                    count = _db_count(self.db_path)
                    print(f"  [伺服器未更新，沿用快取：{self.city_code}，共 {count} 筆]")
                    return count

                resp.raise_for_status()
                text = resp.content.decode("utf-8-sig")
                lines = text.splitlines()
                if len(lines) < 3:
                    return 0

                reader = csv.DictReader(io.StringIO("\n".join([lines[0]] + lines[2:])))
                rows = list(reader)
                count = await asyncio.to_thread(_write_to_db, self.db_path, rows)
                print(f"  [API 下載：{self.city_code}，共 {count} 筆（過濾後），已存入 SQLite]")
                return count

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < 2:
                    print(f"  [下載失敗，第 {attempt + 1} 次重試：{e}]")
                    await asyncio.sleep(1)
                else:
                    print(f"  [下載失敗（已重試 2 次）：{e}]")
            except Exception as e:
                print(f"  [下載失敗：{e}]")
                break

        return 0

    async def query(self, district: str = "", keyword: str = "", limit: int = 20) -> list[dict]:
        await self.ensure_data()
        if not self.db_path.exists():
            return []
        return await asyncio.to_thread(_query_db, self.db_path, district, keyword, limit)
