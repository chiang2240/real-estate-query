"""
主程式入口

用法：
  python main.py              # 更新所有有 source_591_id 的社區
  python main.py --id 1       # 只更新 building_id=1
  python main.py --dry-run    # 只印出結果，不寫入 CSV
"""

import argparse
import csv
import sys
from pathlib import Path

from fetcher_591 import fetch

DATA_DIR = Path(__file__).parent.parent / "data"
BUILDINGS_CSV = DATA_DIR / "buildings.csv"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"

TRANSACTION_FIELDS = [
    "building_id", "source", "floor", "date_roc", "date_iso",
    "total_price_wan", "unit_price_wan", "size_ping", "layout", "parking",
]


def load_buildings(target_id: int | None) -> list[dict]:
    with open(BUILDINGS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if target_id is not None:
        rows = [r for r in rows if r["id"] == str(target_id)]
    # 只處理有 591 ID 的社區
    return [r for r in rows if r.get("source_591_id", "").strip()]


def load_existing_transactions() -> list[dict]:
    if not TRANSACTIONS_CSV.exists():
        return []
    with open(TRANSACTIONS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_transactions(records: list[dict]) -> None:
    with open(TRANSACTIONS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRANSACTION_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def merge(existing: list[dict], new: list[dict], building_id: str) -> list[dict]:
    """保留舊資料中非本次更新社區的列，再加入新抓的資料。"""
    kept = [r for r in existing if r["building_id"] != building_id]
    return kept + new


def main() -> None:
    parser = argparse.ArgumentParser(description="591 實價登錄爬蟲")
    parser.add_argument("--id", type=int, default=None, help="只更新指定 building_id")
    parser.add_argument("--dry-run", action="store_true", help="只印出結果，不寫入 CSV")
    args = parser.parse_args()

    buildings = load_buildings(args.id)
    if not buildings:
        print("找不到符合條件的社區（或該社區無 591 ID）。")
        sys.exit(0)

    all_transactions = load_existing_transactions()

    for b in buildings:
        bid = b["id"]
        name = b["name"]
        sid = int(b["source_591_id"])
        print(f"抓取中：[{bid}] {name}（591 ID: {sid}）")

        new_records = fetch(building_id=int(bid), source_591_id=sid)
        print(f"  取得 {len(new_records)} 筆成交紀錄")

        if args.dry_run:
            for r in new_records:
                print("  ", r)
        else:
            all_transactions = merge(all_transactions, new_records, bid)

    if not args.dry_run:
        save_transactions(all_transactions)
        print(f"\n已更新 {TRANSACTIONS_CSV}")


if __name__ == "__main__":
    main()
