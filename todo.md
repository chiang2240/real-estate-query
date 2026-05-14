# 優化 Todo

## 待辦事項

- [x] **歷史房價趨勢（近 10 年）**
    - ✅ API 已驗證：`GET /DownloadSeason?season=113S1&type=zip&fileName=lvr_landcsv.zip`
    - 每個 ZIP 含全縣市 CSV（如 `f_lvr_land_a.csv` = 新北市買賣），共 53 季（101S1–115S1）
    - `crawler.py` 新增 `download_history_season(season)`：下載 ZIP → 取出目標城市 CSV → 寫入歷史 SQLite（含 season 欄位）。
    - `lvrs.py` 新增 `get_price_trend(city, district, keyword, seasons)`：按季聚合均價，回傳時間序列。
    - MCP tool `price_trend` + Web UI 折線圖（Chart.js）。

## 已完成

- [x] API 快取 — 本地 JSON 快取（TTL 6 小時），避免重複下載同城市同季資料
- [x] 擴充工具 — 新增 `compare_districts`、`search_by_community` 兩個 Claude tool
- [x] 資料篩選效率 — 先 keyword filter 再 format，減少大城市記憶體用量
- [x] Web UI — FastAPI + 前端，支援視覺化與 CSV 匯出
- [x] AI Prompt 優化 — 提升 Claude 分析深度與商業洞察力
- [x] SQLite 索引 — 取代 JSON 快取，對行政區與門牌建立索引，查詢從全掃改為 SQL WHERE
- [x] Async IO — requests → httpx AsyncClient；FastAPI 端點、lvrs 函式全改 async def
- [x] 交易標的過濾 — 寫入 SQLite 時排除純土地、純車位，統計均價更準確
- [x] 快取分層 — CACHE_TTL 6h（資料本體）+ CACHE_LIST_TTL 24h（Last-Modified 元資料），304 Not Modified 跳過重新下載
- [x] 職責分離 — `crawler.py`（LvrsCrawler）、`models.py`（Pydantic 模型）、精簡 `lvrs.py` 為薄服務層
- [x] 安全 & 錯誤處理 — SSL env var、Timeout、Retry（最多 2 次）
- [x] geocoding.py — requests → httpx
- [x] MCP-1 — 抽出共用 `resolve_address` 至 `geocoding.py`，修復 `api.py` 重複定義
- [x] MCP-2 — 建立 `mcp_server.py`，三個工具改為 `@mcp.tool()`
- [x] MCP-3 — 加入 `cache://cities` Resource
- [x] MCP-4 — SYSTEM_PROMPT 改為 `@mcp.prompt()`，`main.py` 統一 import
- [x] MCP-5 — `api.py` 掛載 `/mcp` streamable-http endpoint
- [x] MCP-6 — 刪除 `main.py` CLI
