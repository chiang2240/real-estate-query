# 專案說明

台灣房價查詢工具，整合實價登錄 open data 與 Claude AI。

## 修改規範

**所有程式碼異動（新增、修改、刪除檔案）都必須先取得使用者同意，再執行。**

流程：
1. 說明打算做什麼、為什麼
2. 等待使用者確認
3. 確認後才動手

## 技術棧

- Python 3.13
- Claude API（`claude-sonnet-4-6`）+ Prompt Caching
- FastAPI + uvicorn
- 實價登錄 open data API

## 啟動方式

```bash
# Web UI
uvicorn api:app --reload

# CLI
python main.py
```

## 核心模組

| 檔案 | 職責 |
|------|------|
| `lvrs.py` | 實價登錄下載、快取、查詢、統計 |
| `geocoding.py` | 地址解析（Google Maps / 正則） |
| `api.py` | FastAPI REST API + 靜態服務 |
| `main.py` | Claude AI CLI 對話介面 |
