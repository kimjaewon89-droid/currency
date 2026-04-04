import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        # 최신 데이터가 위로 오도록 정렬되어 있다면 날짜순으로 재정렬
        df = df.sort_values('Date')
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- 사이드바: 전술 제어판 ---
    st.sidebar.header("🕹️ 전술 제어판")
    
    # 1. 조회 기간 설정 (최근 n일)
    max_days = len(df) # 실제 데이터 개수만큼 제한
    view_days = st.sidebar.slider("조회 기간 설정 (최근 n일)", 90, 1095, 365)
    
    # 2. 유동성 시차 설정
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 21)

    # --- 데이터 처리 ---
    # 선택한 기간만큼 데이터 자르기
    cutoff_date = df['Date'].max() - timedelta(days=view_days)
    df_filtered = df[df['Date'] >= cutoff_date].copy()
    
    # 유동성 시차 적용 (필터링된 데이터 기반)
    df_filtered['Shifted_Liquidity'] = df_filtered['Net_Liquidity'].shift(shift_days)

    st.title("🛡️ Captain's Multi-Layer Tactical Map")
    st.info(f"현재 최근 **{view_days}일** 데이터를 조회 중이며, 유동성 시차는 **{shift_days}일**입니다.")

    # 2행 1열 서브플롯
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        subplot_titles=("<b>[전술 1] 유동성 시차 투영 (Current vs Shifted)</b>", "<b>[전술 2] VIX 공포 지수</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # --- 상단 그래프 (행 1) ---
    # 원본 유동성 (연한 파란색 점선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                   name="Raw Liquidity (Current)", 
                   line=dict(color='rgba(30, 144, 255, 0.4)', width=2, dash='dot')),
        row=1, col=1, secondary_y=False
    )
    
    # 시프트 유동성 (보라색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Shifted_Liquidity'], 
                   name=f"Liquidity (Shifted {shift_days}d)", 
                   line=dict(color='mediumpurple', width=3)),
        row=1, col=1, secondary_y=False
    )

    # S&P 500 (주황색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['SP500'], 
                   name="S&P 500 (Market)", 
                   line=dict(color='darkorange', width=2)),
        row=1, col=1, secondary_y=True
    )

    # --- 하단 그래프 (행 2) ---
    # VIX 지수 (빨간색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['VIX'], 
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

    fig.update_yaxes(title_text="Liquidity ($M)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="S&P 500", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="VIX Index", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
