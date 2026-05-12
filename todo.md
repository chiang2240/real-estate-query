# 優化 Todo

## 進度

- [x] 1. API 快取 — 本地 JSON 快取（TTL 6 小時），避免重複下載同城市同季資料
- [x] 2. 擴充工具 — 新增 `compare_districts`、`price_trend`、`search_by_community` 三個 Claude tool
- [ ] 3. 資料篩選效率 — 先 keyword filter 再 format，減少大城市記憶體用量
- [ ] 4. Web UI — FastAPI + 前端，支援視覺化與 CSV 匯出
