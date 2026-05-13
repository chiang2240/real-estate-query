# 台灣房價查詢

查詢台灣實價登錄成交資料，支援 CLI（Claude AI 對話）與 Web UI 兩種介面。

## 架構

```
real-estate-query/
├── main.py          # CLI 對話介面（Claude AI + tool use + prompt caching）
├── api.py           # FastAPI 後端（REST API + 靜態檔案服務）
├── lvrs.py          # 實價登錄 API 整合（下載、快取、查詢、統計）
├── geocoding.py     # Google Maps Geocoding（地址解析）
├── static/
│   └── index.html   # 前端（Tab 查詢、Chart.js 折線圖、CSV 匯出）
├── .cache/          # 本地 JSON 快取（TTL 6 小時）
└── .env             # API 金鑰設定
```

**資料流：**

```
使用者輸入
  ├── CLI (main.py)  →  Claude AI  →  tool_use  →  lvrs.py / geocoding.py
  └── 瀏覽器        →  api.py     →  直接呼叫  →  lvrs.py / geocoding.py
                                                        ↓
                                              .cache/ (hit) 或 實價登錄 API (miss)
```

兩個入口共用同一套 `lvrs.py` 核心邏輯，快取也共享。

## 安裝

```bash
pip install -r requirements.txt
```

複製 `.env.example` 為 `.env` 並填入金鑰：

```env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_MAPS_API_KEY=AIza...   # 選填，用於精確地址解析
```

> 未設定 Google Maps 金鑰時，自動以正則解析縣市行政區，精度較低。

## 使用

### Web UI

```bash
uvicorn api:app --reload
```

開啟 `http://localhost:8000`，功能：

| Tab | 說明 |
|-----|------|
| 近期成交 | 輸入地址查近期成交案例 |
| 行政區統計 | 均價、最高/最低單價、平均總價 |
| 比較兩區 | 並排比較兩個行政區行情 |
| 價格趨勢 | 折線圖顯示最近 4~6 季均價走勢 |
| 社區搜尋 | 依大樓/社區名稱搜尋 |

每個查詢結果可直接匯出 CSV。

### CLI（Claude AI 對話）

```bash
python main.py
```

以自然語言詢問，Claude 會自動呼叫工具查詢實價登錄資料：

```
你：台北市大安區最近成交行情怎樣？
你：幫我比較新北市板橋區和新莊區
你：富綠旺最近賣多少？
```

指令：`clear` 清除對話紀錄 | `quit` / `exit` 離開

## API 端點

| 方法 | 路徑 | 參數 |
|------|------|------|
| GET | `/api/query` | `address`, `limit` |
| GET | `/api/district-stats` | `address` |
| GET | `/api/compare` | `address1`, `address2` |
| GET | `/api/trend` | `address`, `seasons` |
| GET | `/api/community` | `city`, `keyword`, `limit` |
| GET | `/api/export/csv` | `address`, `limit` |

互動式文件：`http://localhost:8000/docs`

## 資料來源

- **實價登錄**：[內政部不動產成交案件實際資訊資料供應系統](https://plvr.land.moi.gov.tw/DownloadOpenData)
- 查詢近 3 季資料，每筆快取 6 小時
- 僅含買賣類（category A），不含租賃

## Claude Tools

CLI 模式下 Claude 可呼叫以下工具：

| Tool | 說明 |
|------|------|
| `query_lvrs` | 查近期成交案例或行政區統計 |
| `compare_districts` | 比較兩行政區房價 |
| `price_trend` | 查詢近幾季均價趨勢 |
| `search_by_community` | 依社區/大樓名稱搜尋 |
