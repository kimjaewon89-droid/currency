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
st.title("🛡️ Captain's Multi-Axis Tactical Map")

# 레이아웃 설정: 3개의 Y축을 사용하기 위해 빈 공간 확보
fig = go.Figure()

# 1. 원본 실질 유동성 (연한 파란색 점선) - Y축 1 (왼쪽)
fig.add_trace(go.Scatter(
    x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
    name="Raw Liquidity (Current)", 
    line=dict(color='rgba(30, 144, 255, 0.3)', width=1, dash='dot'),
    yaxis="y1"
))

# 2. 시프트된 실질 유동성 (진한 보라색 실선) - Y축 1 (왼쪽)
fig.add_trace(go.Scatter(
    x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
    name=f"Liquidity (Shifted {shift_days}d)", 
    line=dict(color='mediumpurple', width=3),
    yaxis="y1"
))

# 3. S&P 500 (주황색 실선) - Y축 2 (오른쪽 1)
fig.add_trace(go.Scatter(
    x=df_plot['Date'], y=df_plot['SP500'], 
    name="S&P 500 (Market)", 
    line=dict(color='darkorange', width=2),
    yaxis="y2"
))

# 4. VIX 지수 (빨간색 실선) - Y축 3 (오른쪽 2, 더 바깥쪽)
fig.add_trace(go.Scatter(
    x=df_plot['Date'], y=df_plot['VIX'], 
    name="VIX (Fear Index)", 
    line=dict(color='crimson', width=1.5),
    yaxis="y3"
))

# --- 3중 축 레이아웃 설정 ---
fig.update_layout(
    xaxis=dict(domain=[0, 0.9]), # 오른쪽 축들을 위해 메인 화면을 살짝 좁힘
    yaxis=dict(title="Liquidity ($ Millions)", titlefont=dict(color="mediumpurple"), tickfont=dict(color="mediumpurple")),
    yaxis2=dict(title="S&P 500", titlefont=dict(color="darkorange"), tickfont=dict(color="darkorange"), anchor="x", overlaying="y", side="right"),
    yaxis3=dict(title="VIX Index", titlefont=dict(color="crimson"), tickfont=dict(color="crimson"), anchor="free", overlaying="y", side="right", position=0.98),
    
    title_text=f"<b>[전술 분석] 유동성/주가/변동성 3축 투영 (Shift: {shift_days}일)</b>",
    hovermode="x unified",
    height=750,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_dark" # Captain의 다크모드 취향 저격
)

st.plotly_chart(fig, use_container_width=True)
