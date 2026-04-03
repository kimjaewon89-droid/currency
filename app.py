import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df

df = load_data()

# --- 사이드바: 전술 제어판 ---
st.sidebar.header("🕹️ 전술 제어판")
shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 21)

# --- 데이터 처리 ---
df_plot = df.copy()
df_plot['Shifted_Liquidity'] = df_plot['Net_Liquidity'].shift(shift_days)

# --- 메인 차트 ---
st.title("🛡️ Captain's Liquidity & Volatility Tactical Map")

# 3개의 Y축을 쓰기 위해 레이아웃 최적화
fig1 = make_subplots(specs=[[{"secondary_y": True}]])

# 1. 원본 실질 유동성 (연한 파란색 점선)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
               name="Raw Liquidity (Current)", 
               line=dict(color='rgba(30, 144, 255, 0.3)', width=1, dash='dot')),
    secondary_y=False,
)

# 2. 시프트된 실질 유동성 (진한 보라색 실선)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
               name=f"Liquidity (Shifted {shift_days}d)", 
               line=dict(color='mediumpurple', width=3)),
    secondary_y=False,
)

# 3. VIX 지수 (빨간색 실선 - 공포 지수)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
               name="VIX (Fear Index)", 
               line=dict(color='crimson', width=1.5)),
    secondary_y=True,
)

# 4. S&P 500 (주황색 실선)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
               name="S&P 500 (Market)", 
               line=dict(color='darkorange', width=2)),
    secondary_y=True,
)

fig1.update_layout(
    title_text=f"<b>[전술 분석] 유동성 시차 및 변동성 투영 (Shift: {shift_days}일)</b>",
    hovermode="x unified",
    height=700,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    # Y축 라벨 설정
    yaxis=dict(title="Liquidity ($ Millions)"),
    yaxis2=dict(title="S&P 500 / VIX", overlaying='y', side='right')
)

st.plotly_chart(fig1, use_container_width=True)
