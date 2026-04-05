import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
import os

st.set_page_config(page_title="Liquidity View", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date')

df = load_data()

# 데이터가 없을 경우 경고 후 렌더링 중지
if df.empty:
    st.error("⚠️ 데이터가 없습니다. 사이드바 위의 'Home(main)'으로 이동하여 [최신 데이터 수집] 버튼을 눌러주세요.")
    st.stop()

st.title("🛡️ Liquidity Tactical View")

col1, col2 = st.columns([2, 1])
with col1:
    max_dt = df['Date'].max().to_pydatetime()
    min_dt = df['Date'].min().to_pydatetime()
    start_def = max_dt - timedelta(days=365)
    selected_range = st.slider("📅 기간 설정", min_dt, max_dt, (start_def, max_dt), format="YYYY-MM-DD")
with col2:
    shift = st.number_input("⏳ 유동성 시차(일)", 0, 90, 21)

mask = (df['Date'] >= selected_range[0]) & (df['Date'] <= selected_range[1])
df_plot = df.copy()

if 'Net_Liquidity' in df_plot.columns:
    df_plot['Shifted'] = df_plot['Net_Liquidity'].shift(shift)
else:
    st.warning("Net_Liquidity 데이터를 찾을 수 없습니다.")
    st.stop()

df_final = df_plot.loc[mask]

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                    specs=[[{"secondary_y": True}], [{"secondary_y": False}]])

fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['Net_Liquidity'],
                         name="Raw Liq", line=dict(color='yellow', width=1, dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['Shifted'],
                         name="Shifted Liq", line=dict(color='mediumpurple', width=3)), row=1, col=1)
fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['SP500'],
                         name="S&P 500", line=dict(color='darkorange', width=2)), row=1, col=1, secondary_y=True)

if 'VIX' in df_final.columns:
    fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['VIX'],
                             name="VIX", fill='tozeroy', line=dict(color='crimson')), row=2, col=1)

fig.update_layout(height=800, template="plotly_dark", hovermode="x unified",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

st.plotly_chart(fig, use_container_width=True)