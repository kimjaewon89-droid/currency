import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Captain's Liquidity Radar", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df

df = load_data()

# --- 사이드바 설정 ---
st.sidebar.header("📊 전술 제어판")
# 유동성 선을 며칠이나 뒤로 미룰지 결정 (0일 ~ 30일)
shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 30, 7)

st.title("🛡️ Captain's Liquidity Radar")
st.markdown(f"현재 **{shift_days}일**의 유동성 시차를 적용 중입니다.")

# --- 데이터 전처리: 시프트 적용 ---
df_plot = df.copy()
# 유동성 데이터를 설정한 일수만큼 뒤로 미룹니다.
df_plot['Shifted_Liquidity'] = df_plot['Net_Liquidity'].shift(shift_days)

# --- 그래프 1: 시프트된 유동성 vs S&P 500 ---
fig1 = make_subplots(specs=[[{"secondary_y": True}]])

# 1. 시프트된 실질 유동성 (파란색)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], name=f"Net Liquidity ({shift_days}d Shifted)", 
               line=dict(color='dodgerblue', width=2)),
    secondary_y=False,
)

# 2. S&P 500 (주황색)
fig1.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], name="S&P 500", 
               line=dict(color='darkorange', width=2)),
    secondary_y=True,
)

fig1.update_layout(title_text=f"<b>[전술 1] 유동성 선행 지표 분석 (Shift: {shift_days}일)</b>", height=500)
st.plotly_chart(fig1, use_container_width=True)

# (이후 그래프 2, 3은 기존 코드와 동일하게 유지하거나 추가 가능)
