
"""HW4-4：氣溫預報 Web App（Streamlit）

執行方式：
    streamlit run app.py

重點：畫面上所有數字都是「即時用 SQL 從 data.db 查出來的」，
不是從記憶體或 CSV 讀的。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "data.db"

# 六大區域的顯示順序（和氣象署的排法一致）
REGION_ORDER = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區"]


# --------------------------------------------------------------------------
# 資料庫查詢：每個函式都對應一句 SQL
# --------------------------------------------------------------------------
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """對 data.db 執行一句 SQL，回傳 DataFrame。"""
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_region_names() -> list:
    """列出資料庫裡所有地區名稱。"""
    sql = "SELECT DISTINCT regionName FROM TemperatureForecasts"
    names = query(sql)["regionName"].tolist()
    # 依照固定順序排列，沒在清單裡的就排在後面
    return sorted(names, key=lambda n: REGION_ORDER.index(n) if n in REGION_ORDER else 99)


def get_forecast(region_name: str) -> pd.DataFrame:
    """查出某個地區一週的最高 / 最低氣溫。

    使用參數化查詢（?）而不是字串拼接，避免 SQL injection。
    """
    sql = """
        SELECT dataDate, MinT, MaxT
        FROM TemperatureForecasts
        WHERE regionName = ?
        ORDER BY dataDate
    """
    return query(sql, (region_name,))


# --------------------------------------------------------------------------
# 畫面
# --------------------------------------------------------------------------
st.set_page_config(page_title="氣溫預報 Web App", page_icon="🌡️", layout="wide")
st.title("🌡️ 氣溫預報 Web App")
st.caption("資料來源：中央氣象署開放資料平臺　|　資料儲存：SQLite (data.db)")

if not DB_PATH.exists():
    st.error("找不到 data.db，請先執行 hw4.ipynb 建立資料庫。")
    st.stop()

# ---------------------------------------------------------------------------
# 側邊欄：重新抓取最新預報
# 需要 CWA 授權碼。本機看環境變數 CWA_API_KEY；
# 部署到 Streamlit Cloud 時改在 Settings → Secrets 設定同名的 secret。
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    try:
        if "CWA_API_KEY" in st.secrets:
            return str(st.secrets["CWA_API_KEY"])
    except Exception:
        pass  # 沒有 secrets 檔案時 st.secrets 會拋例外，忽略即可
    return os.getenv("CWA_API_KEY", "")


with st.sidebar:
    st.header("資料")
    updated_at = (
        datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if DB_PATH.exists() else "—"
    )
    st.caption(f"資料庫更新時間：{updated_at}")

    api_key = get_api_key()
    if api_key:
        if st.button("🔄 重新抓取最新預報", use_container_width=True):
            try:
                import weather
                with st.spinner("正在向中央氣象署取得最新預報…"):
                    df_new = weather.refresh_data(api_key)
                st.success(f"已更新 {len(df_new)} 筆資料")
                st.rerun()
            except Exception as error:
                st.error(f"更新失敗：{error}")
    else:
        st.caption(
            "未設定 CWA 授權碼，無法在線上更新。\n\n"
            "本機：`export CWA_API_KEY=\"...\"`\n\n"
            "Streamlit Cloud：Settings → Secrets 新增 `CWA_API_KEY`"
        )


# --- 下拉選單：選擇地區 ---
regions = get_region_names()
selected_region = st.selectbox("選擇地區", regions)

df = get_forecast(selected_region)

if df.empty:
    st.warning(f"資料庫中沒有 {selected_region} 的資料。")
    st.stop()

# --- 摘要數字 ---
col1, col2, col3 = st.columns(3)
col1.metric("一週最高溫", f"{df['MaxT'].max()} °C")
col2.metric("一週最低溫", f"{df['MinT'].min()} °C")
col3.metric("預報天數", f"{len(df)} 天")

# --- 折線圖 ---
st.subheader(f"{selected_region}　一週氣溫趨勢")

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=df["dataDate"], y=df["MaxT"], name="最高溫 MaxT",
        mode="lines+markers+text", line=dict(color="#e53e3e", width=3),
        text=df["MaxT"], textposition="top center",
    )
)
fig.add_trace(
    go.Scatter(
        x=df["dataDate"], y=df["MinT"], name="最低溫 MinT",
        mode="lines+markers+text", line=dict(color="#3182ce", width=3),
        text=df["MinT"], textposition="bottom center",
        fill="tonexty", fillcolor="rgba(120,160,220,0.15)",
    )
)
fig.update_layout(
    xaxis_title="日期", yaxis_title="氣溫 (°C)",
    hovermode="x unified", height=430,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(t=40, b=40),
)
st.plotly_chart(fig, use_container_width=True)

# --- 表格 ---
st.subheader(f"{selected_region}　一週氣溫資料")
table = df.rename(columns={"dataDate": "日期", "MinT": "最低溫 (°C)", "MaxT": "最高溫 (°C)"})
st.dataframe(table, use_container_width=True, hide_index=True)

# --- 讓助教看到確實是用 SQL 查的 ---
with st.expander("查看本頁使用的 SQL"):
    st.code(
        "-- 下拉選單的地區清單\n"
        "SELECT DISTINCT regionName FROM TemperatureForecasts;\n\n"
        "-- 選定地區的一週氣溫\n"
        "SELECT dataDate, MinT, MaxT\n"
        "FROM TemperatureForecasts\n"
        f"WHERE regionName = '{selected_region}'\n"
        "ORDER BY dataDate;",
        language="sql",
    )
