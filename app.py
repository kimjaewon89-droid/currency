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
        df = df.sort_values('Date')
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- 사이드바: 전술 제어판 ---
    st.sidebar.header("🕹️ 전술 제어판")
    
    # 1. 범위형 기간 설정 (시작일 ~ 종료일)
    min_date = df['Date'].min().to_pydatetime()
    max_date = df['Date'].max().to_pydatetime()
    
    # 슬라이더에서 날짜 범위를 선택 (기본값은 최근 1년)
    selected_range = st.sidebar.slider(
        "조회 기간 범위 설정",
        min_value=min_date,
        max_value=max_date,
        value=(max_date - timedelta(days=365), max_date),
        format="YYYY-MM-DD"
    )
    
    start_date, end_date = selected_range
    
    # 2. 유동성 시차 설정
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 60, 21)

    # --- 데이터 처리 ---
    # 선택된 날짜 범위로 데이터 필터링
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    df_filtered = df.loc[mask].copy()
    
    # [중요] 시차 적용은 전체 데이터에서 미리 해야 경계선 데이터가 끊기지 않습니다.
    # 전체 데이터 기준 시프트 후 필터링된 구간에 다시 매핑
    df['Shifted_Liquidity'] = df['Net_Liquidity'].shift(shift_days)
    df_filtered = df.loc[mask].copy()

    st.title("🛡️ Captain's Multi-Layer Tactical Map")
    st.info(f"📅 **조회 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} | ⏳ **시차:** {shift_days}일")

    # 2행 1열 서브플롯
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        subplot_titles=("<b>[전술 1] 유동성 시차 투영 (Current vs Shifted)</b>", "<b>[전술 2] VIX 공포 지수</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # --- 상단 그래프 (행 1) ---
    # 원본 유동성 (노란색 점선 - Captain의 요청 컬러 반영)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                   name="Raw Liquidity (Current)", 
                   line=dict(color='yellow', width=1, dash='dot')),
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
