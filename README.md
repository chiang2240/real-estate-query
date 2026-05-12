# real-estate-query

台灣不動產實價登錄資料查詢與彙整工具。

## 專案目的

針對特定地址或社區，自動抓取並彙整來自 591、5168比價王等平台的實價登錄成交紀錄，輸出為標準化的 CSV 資料，方便長期追蹤與比較分析。

---

## 目錄結構

```
real-estate-query/
├── data/
│   ├── buildings.csv        # 社區基本資料（一列一社區）
│   ├── transactions.csv     # 成交紀錄（一列一筆成交）
│   └── sources.csv          # 各社區資料來源 URL
├── scraper/
│   ├── main.py              # 主程式入口
│   ├── fetcher_591.py       # 591 實價登錄爬蟲
│   └── requirements.txt     # Python 套件需求
└── README.md
```

---

## 資料格式

### `data/buildings.csv`

| 欄位 | 說明 |
|------|------|
| `id` | 社區唯一識別碼（流水號） |
| `name` | 社區名稱 |
| `address` | 完整地址 |
| `city` | 縣市 |
| `district` | 行政區 |
| `age_years` | 屋齡（年） |
| `floors` | 總樓層數 |
| `size_min_ping` | 最小坪數 |
| `size_max_ping` | 最大坪數 |
| `source_591_id` | 591 社區 ID（若有） |
| `notes` | 備註 |

### `data/transactions.csv`

| 欄位 | 說明 |
|------|------|
| `building_id` | 對應 buildings.csv 的 id |
| `source` | 資料來源（591 / 5168比價王 / 內政部） |
| `floor` | 樓層 |
| `date_roc` | 成交日期（民國，格式：114-12） |
| `date_iso` | 成交日期（西元，格式：2025/12） |
| `total_price_wan` | 總價（萬元） |
| `unit_price_wan` | 單價（萬/坪） |
| `size_ping` | 建物坪數 |
| `layout` | 格局（如：3房） |
| `parking` | 車位（有 / 無） |

### `data/sources.csv`

| 欄位 | 說明 |
|------|------|
| `building_id` | 對應 buildings.csv 的 id |
| `source_name` | 來源名稱 |
| `url` | 來源 URL |

---

## 快速開始

### 安裝相依套件

```bash
cd scraper
pip install -r requirements.txt
```

### 執行爬蟲

```bash
# 抓取所有已設定社區的最新成交紀錄
python main.py

# 只抓取特定社區（依 building_id）
python main.py --id 1
```

執行後會自動更新 `data/transactions.csv`。

---

## 資料來源

- [591 實價登錄](https://market.591.com.tw/)
- [5168 實價登錄比價王](https://price.houseprice.tw/)
- [內政部不動產交易實價查詢服務網](https://lvr.land.moi.gov.tw/)
