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

# 1. 서브플롯 생성 (2개의 Y축을 기본으로 생성)
fig = make_subplots(specs=[[{"secondary_y": True}]])

# 2. 유동성 데이터 (왼쪽 Y축)
fig.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
               name="Raw Liquidity (Current)", 
               line=dict(color='rgba(30, 144, 255, 0.3)', width=1, dash='dot')),
    secondary_y=False
)

fig.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
               name=f"Liquidity (Shifted {shift_days}d)", 
               line=dict(color='mediumpurple', width=3)),
    secondary_y=False
)

# 3. S&P 500 (오른쪽 Y축 1)
fig.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
               name="S&P 500 (Market)", 
               line=dict(color='darkorange', width=2)),
    secondary_y=True
)

# 4. VIX 지수 (오른쪽 Y축 2 - 독립 스케일 부여)
# VIX의 가독성을 위해 별도의 축 설정을 update_layout에서 진행
fig.add_trace(
    go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
               name="VIX (Fear Index)", 
               line=dict(color='crimson', width=1.5)),
    secondary_y=True
)

# --- 레이아웃 및 3중 축 설정 ---
# VIX와 S&P 500이 같은 secondary_y를 쓰되, VIX의 범위를 강제로 조정하여 겹치지 않게 만듭니다.
fig.update_layout(
    title_text=f"<b>[전술 분석] 유동성/주가/변동성 투영 (Shift: {shift_days}일)</b>",
    hovermode="x unified",
    height=750,
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    
    # 왼쪽 축: 유동성
    yaxis=dict(title="Liquidity ($ Millions)", titlefont=dict(color="mediumpurple"), tickfont=dict(color="mediumpurple")),
    
    # 오른쪽 축: S&P 500과 VIX (VIX가 바닥에 깔리지 않게 스케일링 전략 수정)
    yaxis2=dict(
        title="S&P 500", 
        titlefont=dict(color="darkorange"), 
        tickfont=dict(color="darkorange"),
        side="right"
    )
)

# VIX 데이터를 위해 추가적인 독립 축을 생성하는 대신, 
# 사용자가 직관적으로 볼 수 있도록 VIX 전용 차트를 아래에 하나 더 배치하거나 
# 혹은 Plotly의 yaxis3 레이아웃 충돌을 피하기 위해 설정을 정교화합니다.
fig.update_layout(
    yaxis3=dict(
        title="VIX Index",
        titlefont=dict(color="crimson"),
        tickfont=dict(color="crimson"),
        anchor="free",
        overlaying="y",
        side="right",
        position=0.95
    )
)
# VIX 트레이스의 y축을 y3로 강제 지정
fig.data[3].update(yaxis="y3")

st.plotly_chart(fig, use_container_width=True)
