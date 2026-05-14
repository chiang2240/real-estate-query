# 優化 Todo

## 待辦事項 (Refactor & Polish Phase)

### MCP 架構優化

- [x] **MCP-1. 抽出共用 `resolve_address`（高）**
    - `main.py` 與 `api.py` 各有一份相同邏輯，抽到 `geocoding.py` 統一管理。

- [x] **MCP-2. 建立 `mcp_server.py`，移植三個工具（高）**
    - 使用 `mcp` Python SDK（`FastMCP`）建立 MCP server。
    - 將 `query_lvrs`、`compare_districts`、`search_by_community` 改為 `@mcp.tool()`。
    - 工具可被 Claude Desktop、Claude Code 等任何 MCP client 直接使用。

- [x] **MCP-3. 加入 `cache://cities` Resource（中）**
    - 以 `@mcp.resource()` 列出 `.cache/` 目錄內已快取的城市清單。
    - 讓模型可感知哪些資料已在本機，無需盲目 tool call。

- [x] **MCP-4. 搬移 SYSTEM_PROMPT 為 MCP Prompt（中）**
    - 將 `main.py` 裡的 `SYSTEM_PROMPT` 改為 `@mcp.prompt()`。
    - 跨 session、跨 client 可重用同一份 prompt。

- [x] **MCP-5. `api.py` 加入 MCP streamable-http transport（低）**
    - REST API 與 MCP endpoint 共用同一個 FastAPI app。
    - 遠端 MCP client 可直接連線，不需本機啟動獨立 server。

- [x] **MCP-6. 刪除 `main.py` CLI（低）**
    - MCP server 建好後，Claude Desktop / Claude Code 取代手刻的對話迴圈。
    - 移除重複的 tool dispatch、token 計算、prompt caching 邏輯。

### 後端架構

- [x] **1. 職責分離 (Separation of Concerns)**
    - 新增 `models.py`：Pydantic `TransactionRecord`、`DistrictStats`，取代 dict 傳遞。
    - 新增 `crawler.py`：`LvrsCrawler` 類別，封裝 HTTP 下載、CSV 解析、SQLite 寫入。
    - 精簡 `lvrs.py` 為薄服務層，只保留 `search_transactions`、`get_district_stats`。

- [ ] **2. 地址解析精確度**
    - `geocoding.py` 加入台灣 22 縣市 × 行政區硬編碼對照表。
    - `parse_address` 改為先查表再 regex，避免「宜蘭市」等誤判。
    - ~~同步修掉 `requests` → `httpx` 隱患（已從 requirements.txt 移除）。~~ ✅ 已完成

- [x] **3. 安全 & 錯誤處理**
    - SSL：新增 `LVRS_VERIFY_SSL` 環境變數（預設 `false`），啟動時印警告。
    - Timeout：`httpx.Timeout(connect=5.0, read=20.0)` 取代固定 30s。
    - Retry：下載失敗最多重試 2 次（間隔 1s），不引入外部套件。

### 前端 (`static/index.html`)

- [ ] **4. 狀態管理 + JS 組件化**
    - 建立 `state` 物件統一管理查詢狀態（當前 tab、地址、排序欄位）。
    - 拆出 `renderTable(records)`、`renderStats(data)`、`renderCompare(data)` 純渲染函式。
    - `<th>` 點擊升/降冪排序。

- [ ] **5. 縣市 / 行政區連動下拉選單**
    - 22 縣市 + 對應行政區 `<select>`，取代純文字 input，消除台/臺輸入歧義。
    - 「社區搜尋」保留縣市下拉 + 關鍵字自由輸入。

- [ ] **6. CSV 匯出改 fetch + Blob**
    - 移除 `window.location.href` 跳轉。
    - 改用 `fetch` → `res.blob()` → `URL.createObjectURL` 觸發下載。
    - 失敗時於頁面顯示錯誤訊息，不離開當前頁面。

## 已完成

- [x] 1. API 快取 — 本地 JSON 快取（TTL 6 小時），避免重複下載同城市同季資料
- [x] 2. 擴充工具 — 新增 `compare_districts`、`price_trend`、`search_by_community` 三個 Claude tool
- [x] 3. 資料篩選效率 — 先 keyword filter 再 format，減少大城市記憶體用量
- [x] 4. Web UI — FastAPI + 前端，支援視覺化與 CSV 匯出
- [x] 5. AI Prompt 優化 — 提升 Claude 分析深度與商業洞察力
- [x] 6. SQLite 索引 — 取代 JSON 快取，對行政區與門牌建立索引，查詢從全掃改為 SQL WHERE
- [x] 7. Async IO — requests → httpx AsyncClient；FastAPI 端點、lvrs 函式全改 async def
- [x] 8. 交易標的過濾 — 寫入 SQLite 時排除純土地、純車位，統計均價更準確
- [x] 9. 快取分層 — CACHE_TTL 6h（資料本體）+ CACHE_LIST_TTL 24h（Last-Modified 元資料），304 Not Modified 跳過重新下載
