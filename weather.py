"""HW4 資料擷取腳本：CWA API → 六大區域一週氣溫 → weather_data.csv + data.db

執行方式：
    export CWA_API_KEY="你的授權碼"
    python weather.py

這支程式做三件事：
    1. 呼叫中央氣象署開放資料 API 取得未來一週的氣溫預報（JSON）
    2. 解析 JSON，整理出六大區域每日的最高／最低氣溫
    3. 同時輸出 weather_data.csv 與 SQLite 資料庫 data.db
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict

import pandas as pd
import requests
import urllib3

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

# 👉 換成你自己申請的授權碼，或設定環境變數 CWA_API_KEY
MY_API_KEY = "CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
API_KEY = os.getenv("CWA_API_KEY", "").strip() or MY_API_KEY

BASE_URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi"

PRIMARY_DATASET = "F-A0010-001"   # 作業指定：一週農業氣象預報（目前已下架）
FALLBACK_DATASET = "F-C0032-005"  # 替代：一般天氣預報－一週縣市天氣預報

REGIONS = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區"]

# 氣象署分區：縣市 → 六大區域
REGION_OF_COUNTY = {
    "臺北市": "北部地區", "新北市": "北部地區", "基隆市": "北部地區",
    "桃園市": "北部地區", "新竹縣": "北部地區", "新竹市": "北部地區",
    "苗栗縣": "中部地區", "臺中市": "中部地區", "彰化縣": "中部地區",
    "南投縣": "中部地區", "雲林縣": "中部地區",
    "嘉義縣": "南部地區", "嘉義市": "南部地區", "臺南市": "南部地區",
    "高雄市": "南部地區", "屏東縣": "南部地區",
    "宜蘭縣": "東北部地區",
    "花蓮縣": "東部地區",
    "臺東縣": "東南部地區",
}

DAYS = 7
CSV_PATH = "weather_data.csv"
DB_PATH = "data.db"
TABLE_NAME = "TemperatureForecasts"


# ---------------------------------------------------------------------------
# 1. 取得資料
# ---------------------------------------------------------------------------
def fetch_dataset(dataset_id: str) -> dict:
    """呼叫 CWA API 取得 JSON。

    有些校園或公司網路會做 SSL 攔截，導致憑證驗證失敗。
    這裡先用正常的驗證連線，只有在真的遇到 SSLError 時才退而求其次
    關閉驗證重試一次，並明確警告使用者。
    """
    url = f"{BASE_URL}/{dataset_id}"
    params = {"Authorization": API_KEY, "downloadType": "WEB", "format": "JSON"}

    try:
        response = requests.get(url, params=params, timeout=60)
    except requests.exceptions.SSLError:
        print("⚠️  SSL 憑證驗證失敗，改用未驗證連線重試（請確認你的網路環境是否可信）")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, params=params, timeout=60, verify=False)

    response.raise_for_status()
    return response.json()


def fetch_forecast() -> tuple:
    """先試作業指定的資料集，失敗就改用替代資料集。回傳 (dataset_id, data)。"""
    try:
        data = fetch_dataset(PRIMARY_DATASET)
        print(f"✅ 成功取得 {PRIMARY_DATASET}（一週農業氣象預報）")
        return PRIMARY_DATASET, data
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "?"
        print(f"⚠️  {PRIMARY_DATASET} 無法取得（HTTP {status}），改用 {FALLBACK_DATASET}")
        data = fetch_dataset(FALLBACK_DATASET)
        print(f"✅ 成功取得 {FALLBACK_DATASET}（一週縣市天氣預報）")
        return FALLBACK_DATASET, data


# ---------------------------------------------------------------------------
# 2. 解析 JSON，取出每日最高／最低氣溫
# ---------------------------------------------------------------------------
def extract_from_county_forecast(data: dict) -> pd.DataFrame:
    """F-C0032-005：縣市 × 日夜 → 六大區域 × 每日。"""
    bucket = defaultdict(lambda: {"MaxT": [], "MinT": []})

    for location in data["cwaopendata"]["dataset"]["location"]:
        region = REGION_OF_COUNTY.get(location["locationName"])
        if region is None:          # 澎湖、金門、連江屬離島，不在六大區域內
            continue
        for element in location["weatherElement"]:
            name = element["elementName"]
            if name not in ("MaxT", "MinT"):
                continue
            for slot in element["time"]:
                date = slot["startTime"][:10]
                bucket[(region, date)][name].append(int(slot["parameter"]["parameterName"]))

    dates = sorted({date for _region, date in bucket})[:DAYS]

    rows = []
    for region in REGIONS:
        for date in dates:
            values = bucket.get((region, date))
            if not values or not values["MaxT"] or not values["MinT"]:
                continue
            rows.append({
                "regionName": region,
                "dataDate": date,
                "MinT": min(values["MinT"]),
                "MaxT": max(values["MaxT"]),
            })
    return pd.DataFrame(rows)


def extract_from_agr_forecast(data: dict) -> pd.DataFrame:
    """F-A0010-001：本來就是區域 × 每日的結構。"""
    locations = (
        data["cwaopendata"]["resources"]["resource"]["data"]
        ["agrWeatherForecasts"]["weatherForecasts"]["location"]
    )

    rows = []
    for region in locations:
        name = region["locationName"]
        maxt_daily = region["weatherElements"]["MaxT"]["daily"]
        mint_daily = region["weatherElements"]["MinT"]["daily"]
        for maxt, mint in zip(maxt_daily, mint_daily):
            rows.append({
                "regionName": name,
                "dataDate": maxt["dataDate"],
                "MinT": int(mint["temperature"]),
                "MaxT": int(maxt["temperature"]),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. 輸出 CSV 與 SQLite
# ---------------------------------------------------------------------------
def save_csv(df: pd.DataFrame) -> None:
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"💾 已輸出 {CSV_PATH}（{len(df)} 筆）")


def save_sqlite(df: pd.DataFrame) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        cursor.execute(f"""
            CREATE TABLE {TABLE_NAME} (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                regionName TEXT NOT NULL,
                dataDate   TEXT NOT NULL,
                MaxT       INTEGER,
                MinT       INTEGER
            )
        """)
        cursor.executemany(
            f"INSERT INTO {TABLE_NAME} (regionName, dataDate, MaxT, MinT) VALUES (?, ?, ?, ?)",
            df[["regionName", "dataDate", "MaxT", "MinT"]].values.tolist(),
        )
    print(f"💾 已寫入 {DB_PATH} 的 {TABLE_NAME}（{len(df)} 筆）")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def refresh_data(api_key: str = "") -> pd.DataFrame:
    """抓取最新預報、解析、並同時寫入 CSV 與 SQLite，回傳整理好的 DataFrame。

    這個函式讓 Streamlit App 也能直接呼叫，做到「在網頁上按一下就更新資料」，
    不必再回頭跑 notebook。
    """
    global API_KEY
    if api_key:
        API_KEY = api_key.strip()

    if not API_KEY or API_KEY.startswith("CWA-XXXX"):
        raise ValueError("尚未設定 CWA 授權碼")

    dataset_id, data = fetch_forecast()

    if dataset_id == PRIMARY_DATASET:
        df = extract_from_agr_forecast(data)
    else:
        df = extract_from_county_forecast(data)

    if df.empty:
        raise ValueError("沒有解析到任何氣溫資料")

    save_csv(df)
    save_sqlite(df)
    return df


def main() -> None:
    if not API_KEY or API_KEY.startswith("CWA-XXXX"):
        sys.exit("❌ 請先設定你自己的 CWA 授權碼：export CWA_API_KEY=\"...\"")

    dataset_id, data = fetch_forecast()

    if dataset_id == PRIMARY_DATASET:
        df = extract_from_agr_forecast(data)
    else:
        df = extract_from_county_forecast(data)

    if df.empty:
        sys.exit("❌ 沒有解析到任何氣溫資料")

    # 用 json.dumps 觀察整理後的結果
    print("\n整理後的資料（前 3 筆）：")
    print(json.dumps(df.head(3).to_dict("records"), indent=4, ensure_ascii=False))

    print(f"\n共 {len(df)} 筆　|　{df['regionName'].nunique()} 個地區"
          f"　|　{df['dataDate'].nunique()} 天（{df['dataDate'].min()} ~ {df['dataDate'].max()}）\n")

    save_csv(df)
    save_sqlite(df)


if __name__ == "__main__":
    main()
