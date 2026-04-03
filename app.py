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
shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 14) # 최대 45일까지 확장
st.sidebar.markdown(f"**현재 설정:** {shift_days}일 뒤의 주가를 예측 중")

# --- 데이터 처리 ---
df_plot = df.copy()
# 시차를 적용한 새로운 컬럼 생성
df_plot['Shifted_Liquidity'] = df_plot['Net_Liquidity'].shift(shift_days)

# --- 메인 차트 ---
st.title("🛡️ Captain's Liquidity Tactical Map")

fig1 = make_subplots(specs=[[{"secondary_y": True}]])

# 1. 원본 실질 유동성 (연한 파란색 점선 - 현재의 물리적 수치)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
               name="Raw Liquidity (Current)", 
               line=dict(color='rgba(30, 144, 255, 0.3)', width=1, dash='dot')),
    secondary_y=False,
)

# 2. 시프트된 실질 유동성 (진한 보라색 실선 - 미래 예측 지표)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
               name=f"Liquidity (Shifted {shift_days}d)", 
               line=dict(color='mediumpurple', width=3)),
    secondary_y=False,
)

# 3. S&P 500 (주황색 실선 - 실제 시장 성적)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
               name="S&P 500 (Market)", 
               line=dict(color='darkorange', width=2)),
    secondary_y=True,
)

fig1.update_layout(
    title_text=f"<b>[전술 분석] 유동성 시차 투영 (Gap: {shift_days} days)</b>",
    hovermode="x unified",
    height=600,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig1, use_container_width=True)
