import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    # CSV 파일이 없을 경우를 대비한 안전장치
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except:
        st.error("데이터 파일을 찾을 수 없습니다. GitHub Actions가 먼저 실행되어야 합니다.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- 사이드바: 전술 제어판 ---
    st.sidebar.header("🕹️ 전술 제어판")
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 21)

    # --- 데이터 처리 ---
    df_plot = df.copy()
    df_plot['Shifted_Liquidity'] = df_plot['Net_Liquidity'].shift(shift_days)

    st.title("🛡️ Captain's Multi-Layer Tactical Map")

    # 2행 1열의 서브플롯 생성 (행 간격 조절)
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        subplot_titles=("<b>[전술 1] 유동성 vs S&P 500 (시차 반영)</b>", "<b>[전술 2] VIX 공포 지수 추이</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # --- 상단 그래프 (행 1) ---
    # 1. 시프트된 유동성 (보라색 실선)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
                   name=f"Liquidity (Shifted {shift_days}d)", 
                   line=dict(color='mediumpurple', width=3)),
        row=1, col=1, secondary_y=False
    )
    # 2. S&P 500 (주황색 실선)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
                   name="S&P 500 (Market)", 
                   line=dict(color='darkorange', width=2)),
        row=1, col=1, secondary_y=True
    )

    # --- 하단 그래프 (행 2) ---
    # 3. VIX 지수 (빨간색 실선)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
                   name="VIX (Fear Index)", 
                   line=dict(color='crimson', width=2),
                   fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.1)'), # 시각적 강조
        row=2, col=1
    )

    # --- 레이아웃 설정 ---
    fig.update_layout(
        height=800,
        template="plotly_dark",
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # 축 타이틀 설정
    fig.update_yaxes(title_text="Liquidity ($M)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="S&P 500", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="VIX Index", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("데이터가 로드되지 않았습니다.")
