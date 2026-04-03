import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except:
        st.error("데이터 파일을 찾을 수 없습니다.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- 사이드바: 전술 제어판 ---
    st.sidebar.header("🕹️ 전술 제어판")
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 21)

    # --- 데이터 처리 ---
    df_plot = df.copy()
    # 유동성 시차 적용
    df_plot['Shifted_Liquidity'] = df_plot['Net_Liquidity'].shift(shift_days)

    st.title("🛡️ Captain's Multi-Layer Tactical Map")

    # 2행 1열 서브플롯 (상단: 유동성&주가, 하단: VIX)
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        subplot_titles=("<b>[전술 1] 유동성 시차 투영 (Current vs Shifted)</b>", "<b>[전술 2] VIX 공포 지수</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # --- 상단 그래프 (행 1) ---
    # 1. 원본 실질 유동성 (연한 파란색 점선 - 현재 수치)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
                   name="Raw Liquidity (Current)", 
                   line=dict(color='rgba(30, 144, 255, 0.4)', width=1, dash='dot')),
        row=1, col=1, secondary_y=False
    )
    
    # 2. 시프트된 실질 유동성 (진한 보라색 실선 - 미래 예측 지표)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['Shifted_Liquidity'], 
                   name=f"Liquidity (Shifted {shift_days}d)", 
                   line=dict(color='mediumpurple', width=3)),
        row=1, col=1, secondary_y=False
    )

    # 3. S&P 500 (주황색 실선 - 실제 시장 성적)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
                   name="S&P 500 (Market)", 
                   line=dict(color='darkorange', width=2)),
        row=1, col=1, secondary_y=True
    )

    # --- 하단 그래프 (행 2) ---
    # 4. VIX 지수 (빨간색 실선)
    fig.add_trace(
        go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
                   name="VIX (Fear Index)", 
                   line=dict(color='crimson', width=2),
                   fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.1)'),
        row=2, col=1
    )

    # --- 레이아웃 설정 ---
    fig.update_layout(
        height=850,
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # 축 타이틀 및 눈금 최적화
    fig.update_yaxes(title_text="Liquidity ($M)", row=1, col=1, secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="S&P 500", row=1, col=1, secondary_y=True, showgrid=True)
    fig.update_yaxes(title_text="VIX Index", row=2, col=1, showgrid=True)

    st.plotly_chart(fig, use_container_width=True)
