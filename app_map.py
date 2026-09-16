"""HW4 進階版：氣溫預報地圖 Web App（Streamlit + Folium）

左右分欄版面：
    左側 — 台灣地圖，六大區域以圓圈標示，顏色依當日平均氣溫變化
    右側 — 該日各區域的氣溫資料表

執行方式：
    streamlit run app_map.py

資料一律以 SQL 從 data.db 查出，地圖只負責呈現。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

DB_PATH = Path(__file__).parent / "data.db"
TABLE_NAME = "TemperatureForecasts"

REGION_ORDER = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區"]

# 六大區域的代表座標（取該區主要城市位置作為概略中心點）
REGION_COORDS = {
    "北部地區":   (25.03, 121.52),   # 臺北
    "中部地區":   (24.15, 120.68),   # 臺中
    "南部地區":   (22.99, 120.20),   # 臺南
    "東北部地區": (24.76, 121.75),   # 宜蘭
    "東部地區":   (23.98, 121.60),   # 花蓮
    "東南部地區": (22.75, 121.15),   # 臺東
}


# ---------------------------------------------------------------------------
# 資料查詢：全部走 SQL
# ---------------------------------------------------------------------------
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_dates() -> list:
    """取得資料庫裡所有預報日期。"""
    sql = f"SELECT DISTINCT dataDate FROM {TABLE_NAME} ORDER BY dataDate"
    return query(sql)["dataDate"].tolist()


def get_by_date(date: str) -> pd.DataFrame:
    """取出某一天六大區域的氣溫，並算出平均溫度。"""
    sql = f"""
        SELECT regionName, dataDate, MinT, MaxT
        FROM {TABLE_NAME}
        WHERE dataDate = ?
    """
    df = query(sql, (date,))
    if df.empty:
        return df
    df["AvgT"] = ((df["MinT"] + df["MaxT"]) / 2).round(1)
    # 依照固定的區域順序排列
    df["_order"] = df["regionName"].apply(
        lambda n: REGION_ORDER.index(n) if n in REGION_ORDER else 99
    )
    return df.sort_values("_order").drop(columns="_order").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 顏色規則
# ---------------------------------------------------------------------------
def color_by_temperature(avg_temp: float) -> str:
    """依平均氣溫決定圓圈顏色。"""
    if avg_temp < 20:
        return "blue"
    if avg_temp < 25:
        return "green"
    if avg_temp <= 30:
        return "orange"     # folium 沒有標準 yellow，用 orange 代表黃色區間
    return "red"


def temperature_label(avg_temp: float) -> str:
    if avg_temp < 20:
        return "偏涼（< 20°C）"
    if avg_temp < 25:
        return "舒適（20–25°C）"
    if avg_temp <= 30:
        return "溫暖（25–30°C）"
    return "炎熱（> 30°C）"


# ---------------------------------------------------------------------------
# 地圖
# ---------------------------------------------------------------------------
def build_map(df: pd.DataFrame, date: str) -> folium.Map:
    """建立台灣地圖，每個區域畫一個依溫度上色的圓圈。"""
    # 使用 OpenStreetMap 圖磚：完全免金鑰
    # （注意：folium 內建的 CartoDB 圖磚自 2025 年起已改為需要 API key）
    taiwan_map = folium.Map(
        location=[23.8, 121.0],
        zoom_start=7,
        tiles="OpenStreetMap",
    )

    for _, row in df.iterrows():
        region = row["regionName"]
        coords = REGION_COORDS.get(region)
        if coords is None:
            continue

        avg_temp = row["AvgT"]
        color = color_by_temperature(avg_temp)

        popup_html = f"""
            <div style="font-family: sans-serif; min-width: 165px;">
              <h4 style="margin:0 0 6px 0;">{region}</h4>
              <div style="color:#666; font-size:12px; margin-bottom:8px;">{date}</div>
              <table style="font-size:13px; border-spacing:0 3px;">
                <tr><td>最高溫</td><td style="padding-left:12px;"><b>{row['MaxT']} °C</b></td></tr>
                <tr><td>最低溫</td><td style="padding-left:12px;"><b>{row['MinT']} °C</b></td></tr>
                <tr><td>平均溫</td><td style="padding-left:12px;"><b>{avg_temp} °C</b></td></tr>
              </table>
              <div style="margin-top:8px; font-size:12px; color:{color};">
                ● {temperature_label(avg_temp)}
              </div>
            </div>
        """

        # 圓圈大小也隨溫度變化，讓熱區更明顯
        folium.CircleMarker(
            location=coords,
            radius=14 + (avg_temp - 20) * 0.8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=2,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{region}　{row['MinT']}–{row['MaxT']}°C",
        ).add_to(taiwan_map)

        # 在圓圈旁標上區域名稱與平均溫
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(html=f"""
                <div style="font-size:11px; font-weight:600; color:#222;
                            white-space:nowrap; transform:translate(20px,-8px);
                            text-shadow:0 0 3px #fff, 0 0 3px #fff;">
                  {region} {avg_temp}°C
                </div>"""),
        ).add_to(taiwan_map)

    return taiwan_map


# ---------------------------------------------------------------------------
# 畫面
# ---------------------------------------------------------------------------
st.set_page_config(page_title="氣溫預報地圖", page_icon="🗺️", layout="wide")

st.title("🗺️ 台灣氣溫預報地圖")
st.caption("資料來源：中央氣象署開放資料平臺　|　資料儲存：SQLite (data.db)")

if not DB_PATH.exists():
    st.error("找不到 data.db，請先執行 `python weather.py` 或 hw4.ipynb 建立資料庫。")
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


dates = get_dates()
if not dates:
    st.error("資料庫裡沒有任何預報資料。")
    st.stop()

# --- 日期下拉選單 ---
selected_date = st.selectbox("選擇日期", dates)
df = get_by_date(selected_date)

if df.empty:
    st.warning(f"{selected_date} 沒有資料。")
    st.stop()

# --- 左右分欄：地圖在左、表格在右 ---
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader(f"{selected_date} 各區域氣溫分布")
    st_folium(build_map(df, selected_date), height=560, use_container_width=True)

    st.markdown(
        """
        <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:13px; margin-top:-8px;">
          <span>🔵 &lt; 20°C 偏涼</span>
          <span>🟢 20–25°C 舒適</span>
          <span>🟠 25–30°C 溫暖</span>
          <span>🔴 &gt; 30°C 炎熱</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.subheader("當日氣溫資料")

    col1, col2 = st.columns(2)
    col1.metric("全台最高溫", f"{df['MaxT'].max()} °C", help="六大區域中的最高值")
    col2.metric("全台最低溫", f"{df['MinT'].min()} °C", help="六大區域中的最低值")

    table = df[["regionName", "MinT", "MaxT", "AvgT"]].rename(columns={
        "regionName": "地區",
        "MinT": "最低溫 (°C)",
        "MaxT": "最高溫 (°C)",
        "AvgT": "平均溫 (°C)",
    })
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.bar_chart(df.set_index("regionName")[["MinT", "MaxT"]], height=240)

    with st.expander("查看本頁使用的 SQL"):
        st.code(
            f"-- 日期下拉選單\n"
            f"SELECT DISTINCT dataDate FROM {TABLE_NAME} ORDER BY dataDate;\n\n"
            f"-- 選定日期的各區氣溫\n"
            f"SELECT regionName, dataDate, MinT, MaxT\n"
            f"FROM {TABLE_NAME}\n"
            f"WHERE dataDate = '{selected_date}';",
            language="sql",
        )
