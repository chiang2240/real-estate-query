"""
台灣房價查詢助理 CLI
- Claude AI（Prompt Caching）作為對話主體
- 實價登錄 open data 查詢實際成交價
- Google Maps Geocoding 解析地址
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

from geocoding import geocode_address, parse_address
from lvrs import get_district_stats, get_price_trend, search_transactions

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ── System prompt（含六都行情 + 法規稅務 + 購屋流程）──────────────────────────
SYSTEM_PROMPT = """\
你是專業的台灣不動產顧問，擁有以下完整知識：

## 六都房市行情（2025 年參考均價）
| 城市 | 精華區 | 一般區 |
|------|--------|--------|
| 台北市 | 大安/信義/中正 80-150 萬/坪 | 文山/南港/內湖 40-70 萬/坪 |
| 新北市 | 板橋/新莊/三重 30-55 萬/坪 | 淡水/林口/三峽 15-30 萬/坪 |
| 桃園市 | 桃園/中壢 20-38 萬/坪 | 八德/龜山/蘆竹 15-25 萬/坪 |
| 台中市 | 西屯/南屯/西區 30-55 萬/坪 | 北屯/太平/大里 15-25 萬/坪 |
| 台南市 | 東區/北區/安平 20-38 萬/坪 | 仁德/永康/歸仁 12-22 萬/坪 |
| 高雄市 | 左營/前鎮/苓雅 20-38 萬/坪 | 三民/鳳山/楠梓 12-20 萬/坪 |

## 房地合一稅 2.0（2021 年 7 月起）
- 持有 ≤2 年：45%（境內個人）
- >2 年~5 年：35%
- >5 年~10 年：20%
- >10 年：15%
- **自住優惠**（本人/配偶/未成年子女設籍滿 6 年、無出租無營業）：
  獲利 400 萬以內免稅，超過部分稅率 10%

## 囤房稅 2.0（2024 年 7 月起）
非自住住宅持有稅率（全國歸戶）：
- 1 戶：2.0%（最低）
- 2 戶：2.4%
- 3 戶：3.3%
- 4 戶以上：4.8%（最高）
各縣市得在 1.5%~4.8% 間自行設定

## 土地增值稅
- 自用住宅一生一次優惠：10%
- 一般稅率：20%~40%（依漲幅累進）

## 購屋流程
1. 看房議價 → 2. 簽買賣契約（支付訂金/簽約款）→ 3. 申請房貸
→ 4. 用印 → 5. 完稅（契稅 6%、印花稅）→ 6. 移轉登記 → 7. 交屋

## 貸款參考（2025）
- 首購：最高 8 成，利率約 1.8~2.5%（浮動）
- 第 2 戶：最高 6 成，利率較高
- 青安貸款：最高 1,000 萬，優惠利率 1.775%（2025 年）
- 寬限期：通常 2~3 年

## 回答原則
1. 優先使用實價登錄查詢結果提供具體數據
2. 結合區域行情做合理性分析
3. 提醒可能涉及的稅務影響
4. 語言：繁體中文，條理清晰，數字精準
5. 若資訊不足，主動說明並建議查詢方向
"""

# ── Claude Tool 定義 ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "query_lvrs",
        "description": (
            "查詢台灣實價登錄的實際成交資料。"
            "當使用者詢問特定地址、社區、行政區的成交價或周邊行情時使用。"
            "可查近期成交案例清單，或取得行政區統計均價。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "查詢地址或行政區，例如：'台北市大安區忠孝東路四段' 或 '新北市板橋區'",
                },
                "query_type": {
                    "type": "string",
                    "enum": ["nearby", "district_stats"],
                    "description": "nearby：取近期成交案例清單；district_stats：取行政區統計均價",
                },
            },
            "required": ["address", "query_type"],
        },
    },
    {
        "name": "compare_districts",
        "description": (
            "比較兩個行政區的房價統計（均價、最高/最低單價、平均總價）。"
            "當使用者想比較兩個地區的行情差異時使用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address1": {
                    "type": "string",
                    "description": "第一個地址或行政區，例如：'台北市大安區'",
                },
                "address2": {
                    "type": "string",
                    "description": "第二個地址或行政區，例如：'台北市信義區'",
                },
            },
            "required": ["address1", "address2"],
        },
    },
    {
        "name": "price_trend",
        "description": (
            "查詢某行政區近幾季的房價趨勢，了解價格是上漲還是下跌。"
            "當使用者詢問趨勢、漲跌、近期走向時使用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "行政區，例如：'台北市大安區'",
                },
                "seasons": {
                    "type": "integer",
                    "description": "查詢季數（預設 4 季，最多 6 季）",
                },
            },
            "required": ["address"],
        },
    },
    {
        "name": "search_by_community",
        "description": (
            "用社區名稱或大樓名稱搜尋實價登錄成交紀錄。"
            "當使用者提到特定社區、大樓名稱時使用，例如：'帝寶'、'富綠旺'。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "縣市，例如：'台北市'、'新北市'",
                },
                "keyword": {
                    "type": "string",
                    "description": "社區或大樓名稱關鍵字",
                },
            },
            "required": ["city", "keyword"],
        },
    },
]


# ── 地址解析輔助 ──────────────────────────────────────────────────────────────
def resolve_address(address: str) -> tuple[str, str, str]:
    """回傳 (city, district, formatted_address)。"""
    city = district = ""
    if GOOGLE_MAPS_KEY:
        loc = geocode_address(address, GOOGLE_MAPS_KEY)
        if loc:
            city = loc.get("city", "")
            district = loc.get("district", "")
            address = loc.get("formatted_address", address)
    if not city:
        city, district = parse_address(address)
    return city, district, address


# ── Tool 執行邏輯（dispatcher）────────────────────────────────────────────────
def run_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "query_lvrs":
            return _tool_query_lvrs(tool_input)
        if tool_name == "compare_districts":
            return _tool_compare_districts(tool_input)
        if tool_name == "price_trend":
            return _tool_price_trend(tool_input)
        if tool_name == "search_by_community":
            return _tool_search_community(tool_input)
        return json.dumps({"error": f"未知工具：{tool_name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _tool_query_lvrs(inp: dict) -> str:
    address = inp.get("address", "")
    query_type = inp.get("query_type", "nearby")
    city, district, address = resolve_address(address)
    if not city:
        return json.dumps({"error": "無法識別縣市，請提供更完整的地址（含縣市名）"}, ensure_ascii=False)
    if query_type == "district_stats":
        result = get_district_stats(city, district)
    else:
        transactions = search_transactions(city, district=district, limit=15)
        result = {"查詢地址": address, "城市": city, "行政區": district,
                  "成交案例數": len(transactions), "最近成交": transactions}
    return json.dumps(result, ensure_ascii=False, default=str)


def _tool_compare_districts(inp: dict) -> str:
    city1, district1, _ = resolve_address(inp.get("address1", ""))
    city2, district2, _ = resolve_address(inp.get("address2", ""))
    if not city1 or not city2:
        return json.dumps({"error": "無法識別其中一個縣市，請提供完整地址"}, ensure_ascii=False)
    stats1 = get_district_stats(city1, district1)
    stats2 = get_district_stats(city2, district2)
    result = {
        f"{city1}{district1}": stats1,
        f"{city2}{district2}": stats2,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


def _tool_price_trend(inp: dict) -> str:
    address = inp.get("address", "")
    n_seasons = min(int(inp.get("seasons", 4)), 6)
    city, district, _ = resolve_address(address)
    if not city:
        return json.dumps({"error": "無法識別縣市，請提供更完整的地址（含縣市名）"}, ensure_ascii=False)
    result = get_price_trend(city, district, n_seasons)
    return json.dumps(result, ensure_ascii=False, default=str)


def _tool_search_community(inp: dict) -> str:
    city = inp.get("city", "")
    keyword = inp.get("keyword", "")
    if not city or not keyword:
        return json.dumps({"error": "請提供縣市與社區名稱"}, ensure_ascii=False)
    transactions = search_transactions(city, keyword=keyword, limit=20)
    result = {
        "縣市": city,
        "關鍵字": keyword,
        "成交案例數": len(transactions),
        "成交紀錄": transactions,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


# ── Token 用量顯示 ──────────────────────────────────────────────────────────────
def print_usage(usage: anthropic.types.Usage) -> None:
    parts = []
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    if cw:
        parts.append(f"cache_write={cw}")
    if cr:
        parts.append(f"cache_read={cr}")
    parts += [f"input={usage.input_tokens}", f"output={usage.output_tokens}"]
    print(f"  [Token: {' | '.join(parts)}]")


# ── 單輪對話（含 tool use 迴圈）──────────────────────────────────────────────
def call_claude(messages: list) -> list:
    """執行一次完整的 Claude 對話（含自動工具呼叫），回傳更新後的 messages。"""
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # Prompt Caching
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        print_usage(response.usage)

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # 輸出文字回應
        for block in assistant_content:
            if block.type == "text":
                print(f"\n助理：{block.text}")

        # 無工具呼叫 → 結束
        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        if response.stop_reason == "end_turn" or not tool_uses:
            break

        # 執行工具並回傳結果
        tool_results = []
        for tu in tool_uses:
            print(f"\n  [工具呼叫：{tu.name} {tu.input}]")
            result_str = run_tool(tu.name, tu.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tu.id, "content": result_str}
            )
        messages.append({"role": "user", "content": tool_results})

    return messages


# ── 主程式 CLI ─────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 55)
    print("  台灣房價查詢助理（實價登錄 + Claude AI）")
    print("=" * 55)
    print("  輸入地址或社區查詢實際成交價，或直接問房市問題")
    print("  指令：clear 清除對話 | quit / exit 離開")
    print("=" * 55)

    messages: list = []

    while True:
        try:
            user_input = input("\n你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再見！")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "離開", "退出"):
            print("再見！")
            sys.exit(0)

        if user_input.lower() in ("clear", "清除"):
            messages = []
            print("  對話已清除。")
            continue

        messages.append({"role": "user", "content": user_input})
        messages = call_claude(messages)


if __name__ == "__main__":
    main()
