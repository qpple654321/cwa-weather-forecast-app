# HW4：氣溫預報 Web App（CWA API + SQLite + Streamlit）

用中央氣象署（CWA）開放資料 API 取得台灣六大區域一週的氣溫預報，
分析 JSON 取出每日最高／最低氣溫，存進 SQLite，再用 Streamlit 做成互動式 Web App。

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `hw4.ipynb` | 主要繳交檔，包含 HW4-1 ~ HW4-4 四大題 |
| `app.py` | HW4-4 的 Streamlit Web App：下拉選單 + 折線圖 + 表格 |
| `app_map.py` | 進階版：Folium 台灣地圖 + 左右分欄版面 |
| `weather.py` | 獨立的資料擷取腳本，一次產生 CSV 與 SQLite |
| `data.db` | SQLite 資料庫，內含 `TemperatureForecasts` 資料表 |
| `weather_data.csv` | 氣溫資料的 CSV 備份 |
| `requirements.txt` | 套件清單 |

## 兩種 Web App

### 1. `app.py` — 折線圖版（對應 HW4-4 評分項目）

```bash
streamlit run app.py
```

地區下拉選單 → 該區一週的最高／最低氣溫折線圖與資料表，全部以 SQL 從 `data.db` 查出。

### 2. `app_map.py` — 地圖版（進階）

```bash
streamlit run app_map.py
```

左右分欄版面：

- **左側**：Folium 台灣地圖，六大區域以圓圈標示，
  顏色依當日平均氣溫變化 —— 🔵 < 20°C、🟢 20–25°C、🟠 25–30°C、🔴 > 30°C；
  點圓圈會跳出該區的最高／最低／平均溫 popup
- **右側**：當日各區氣溫資料表、全台高低溫摘要與長條圖
- **上方**：日期下拉選單，切換後地圖與表格同步更新

> 底圖使用 OpenStreetMap。folium 內建的 CartoDB 圖磚自 2025 年起已改為需要 API key，
> 直接使用會出現「API KEY REQUIRED」浮水印，所以這裡改用免金鑰的 OSM。

## 更新資料

兩個 App 的側邊欄都有 **🔄 重新抓取最新預報** 按鈕，按下去會直接呼叫 CWA API
並同時更新 `data.db` 與 `weather_data.csv`，不必回頭跑 notebook。

按鈕只在偵測到授權碼時出現：

- 本機：`export CWA_API_KEY="你的授權碼"` 後再啟動 Streamlit
- Streamlit Cloud：**Settings → Secrets** 新增 `CWA_API_KEY = "你的授權碼"`

也可以直接在終端機更新：

```bash
python weather.py
```

## ⚠️ 繳交前一定要做：換成自己的授權碼

課程範例的授權碼**不能**用在繳交的作業上（該題以 0 分計）。

1. 到 [氣象資料開放平臺](https://opendata.cwa.gov.tw/) 註冊會員
2. 在「取得授權碼」頁面複製你的授權碼（格式：`CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`）
3. 二選一設定：
   - **方法 A（推薦）**：終端機執行 `export CWA_API_KEY="你的授權碼"` 後再開 notebook
   - **方法 B**：直接修改 `hw4.ipynb` 裡 `MY_API_KEY = "..."` 這一行

程式不會把授權碼印出來，所以交出去的 notebook 不會夾帶金鑰。

## 執行步驟

### 1. 安裝套件

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 2. 執行 notebook

用 Jupyter 或 VS Code 開啟 `hw4.ipynb`，由上往下全部執行一次。
跑完會產生 `data.db` 與 `weather_data.csv`。

### 3. 啟動 Web App

```bash
streamlit run app.py
```

瀏覽器打開 <http://localhost:8501>，用下拉選單切換地區即可看到折線圖與表格。

## 關於資料來源的異動（重要）

作業說明指定的 **`F-A0010-001`「一週農業氣象預報」目前已從氣象資料開放平臺下架**，
呼叫 API 會回傳 `404 Resouce not found`（在平臺上搜尋「農業」也只剩觀測網旬報／月報）。

因此改用同樣是 CWA 官方、同樣是 JSON、同樣涵蓋未來一週的
**`F-C0032-005`「一般天氣預報－一週縣市天氣預報」**，
再依氣象署分區把 22 個縣市彙整成作業要求的六大區域：

| 區域 | 涵蓋縣市 |
|------|----------|
| 北部地區 | 臺北市、新北市、基隆市、桃園市、新竹縣、新竹市 |
| 中部地區 | 苗栗縣、臺中市、彰化縣、南投縣、雲林縣 |
| 南部地區 | 嘉義縣、嘉義市、臺南市、高雄市、屏東縣 |
| 東北部地區 | 宜蘭縣 |
| 東部地區 | 花蓮縣 |
| 東南部地區 | 臺東縣 |

原始資料是「縣市 × 每 12 小時（日／夜）」，彙整規則為：
同一區域同一天的所有時段中，`MaxT` 取最大值、`MinT` 取最小值。

程式仍會**先嘗試 `F-A0010-001`**，失敗才自動切換到 `F-C0032-005`，
所以原資料集若恢復上架，不用改程式就能繼續使用。

## 對應評分項目

| 題目 | 要求 | 對應位置 |
|------|------|----------|
| HW4-1 (20%) | Requests 調用 CWA API | `hw4.ipynb` → `fetch_dataset()` |
| | `json.dumps` 觀察資料 | HW4-1 Step 4 |
| HW4-2 (20%) | 提取 MaxT / MinT | `extract_from_county_forecast()` |
| | `json.dumps` 觀察提取結果 | HW4-2 Step 2 |
| HW4-3 (20%) | 建立 `data.db` / `TemperatureForecasts` | HW4-3 Step 1 |
| | 列出所有地區名稱 | HW4-3 查詢 1 |
| | 列出中部地區氣溫資料 | HW4-3 查詢 2 |
| HW4-4 (40%) | 下拉選單 | `app.py` → `st.selectbox` |
| | 折線圖與表格 | `app.py` → `st.plotly_chart` / `st.dataframe` |
| | 從 SQLite 用 SQL 查詢 | `app.py` → `query()` / `get_forecast()` |

## 部署成公開網站（Streamlit Community Cloud）

1. 到 <https://share.streamlit.io> 用 GitHub 帳號登入並授權
2. 按 **Create app** → **Deploy a public app from GitHub**
3. 填入：
   - Repository：`<你的帳號>/cwa-weather-forecast-app`
   - Branch：`main`
   - Main file path：`app.py`
4. 按 **Deploy**，等 1～2 分鐘就會拿到 `https://xxx.streamlit.app` 的網址

Streamlit Cloud 會自動依照 `requirements.txt` 安裝套件，
網站讀的是 repo 裡的 `data.db`，所以 `data.db` 必須一起 commit 上去（本專案已包含）。

> note：`data.db` 是執行 notebook 當下抓到的預報快照。
> 想更新網站上的資料，重跑一次 `hw4.ipynb` 產生新的 `data.db`，
> 再 `git commit` + `git push`，Streamlit Cloud 會自動重新部署。
