import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
# 지표 계산 로직 불러오기
from indicators import calculate_indicators, apply_shift

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        # 데이터 로딩 시 기본 지표(Net_Liquidity 등) 계산
        df = calculate_indicators(df)
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.title("🛡️ Captain's Multi-Layer Tactical Map")
    
    # --- [본문 상단 컨트롤러] ---
    ctrl_col1, ctrl_col2 = st.columns([2, 1])
    with ctrl_col1:
        min_date = df['Date'].min().to_pydatetime()
        max_date = df['Date'].max().to_pydatetime()
        selected_range = st.slider(
            "📅 조회 기간 범위 설정", 
            min_date, max_date, 
            (max_date - timedelta(days=365), max_date), 
            format="YYYY-MM-DD"
        )
        start_date, end_date = selected_range

    with ctrl_col2:
        shift_days = st.number_input("⏳ 유동성 시차(Shift) 설정 (일)", 0, 90, 21)

    # --- [사이드바: 지표 선택 스위치] ---
    st.sidebar.header("🕹️ 전술 지표 활성화")
    # 여기서 선택한 값들이 아래 그래프 출력 여부를 결정합니다.
    show_raw_liq = st.sidebar.checkbox("원본 유동성 (Yellow Dot)", value=True)
    show_shifted_liq = st.sidebar.checkbox("시프트 유동성 (Purple Line)", value=True)
    show_vix = st.sidebar.checkbox("VIX 공포 지수 (Red Area)", value=True)

    # --- 데이터 처리 ---
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    # 시차 적용 (전체 데이터 기준 계산 후 필터링)
    df['Shifted_Liquidity'] = apply_shift(df, 'Net_Liquidity', shift_days)
    df_filtered = df.loc[mask].copy()

    # --- 그래프 생성 ---
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        subplot_titles=("<b>[전술 1] 유동성 및 주가 추이</b>", "<b>[전술 2] 시장 변동성(VIX)</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # 1. 원본 유동성 출력 여부 결정
    if show_raw_liq:
        fig.add_trace(
            go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                       name="Raw Liquidity", 
                       line=dict(color='yellow', width=1, dash='dot')),
            row=1, col=1, secondary_y=False
        )
    
    # 2. 시프트 유동성 출력 여부 결정
    if show_shifted_liq:
        fig.add_trace(
            go.Scatter(x=df_filtered['Date'], y=df_filtered['Shifted_Liquidity'], 
                       name=f"Liquidity (Shifted {shift_days}d)", 
                       line=dict(color='mediumpurple', width=3)),
            row=1, col=1, secondary_y=False
        )

    # 3. S&P 500 (항상 표시하거나, 원하시면 이것도 체크박스로 만들 수 있습니다)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['SP500'], 
                   name="S&P 500", 
                   line=dict(color='darkorange', width=2)),
        row=1, col=1, secondary_y=True
    )

    # 4. VIX 지수 출력 여부 결정
    if show_vix:
        fig.add_trace(
            go.Scatter(x=df_filtered['Date'], y=df_filtered['VIX'], 
                       name="VIX Index", 
                       line=dict(color='crimson', width=2),
                       fill='tozeroy', fillcolor='rgba(220, 20, 60, 0.1)'),
            row=2, col=1
        )

    # 레이아웃 설정
    fig.update_layout(
        height=800,
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)
