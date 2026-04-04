import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
# 우리가 만든 파일에서 함수 불러오기
from indicators import calculate_indicators, apply_shift

st.set_page_config(page_title="Captain's Strategic Dashboard", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        # 불러오자마자 지표 계산 적용
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
        min_date, max_date = df['Date'].min().to_pydatetime(), df['Date'].max().to_pydatetime()
        selected_range = st.slider("📅 조회 기간 범위 설정", min_date, max_date, 
                                   (max_date - timedelta(days=365), max_date), format="YYYY-MM-DD")
        start_date, end_date = selected_range

    with ctrl_col2:
        shift_days = st.number_input("⏳ 유동성 시차(Shift) 설정 (일)", 0, 90, 21)

    # --- [사이드바: 지표 선택 스위치] ---
    st.sidebar.header("🕹️ 지표 활성화")
    show_raw_liq = st.sidebar.checkbox("실시간 유동성 (Yellow Dot)", value=True)
    show_shifted_liq = st.sidebar.checkbox("시프트 유동성 (Purple)", value=True)
    show_vix = st.sidebar.checkbox("VIX 공포 지수 (Red)", value=True)
    # show_m2 = st.sidebar.checkbox("M2 통화량 (Green)", value=False) # 향후 확장용

    # --- 데이터 처리 ---
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    df['Shifted_Liquidity'] = apply_shift(df, 'Net_Liquidity', shift_days)
    df_filtered = df.loc[mask].copy()

    # --- 그래프 생성 ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])

    # 사이드바 선택에 따른 동적 그래프 추가
    if show_raw_liq:
        fig.add_trace(go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                      name="Raw Liquidity", line=dict(color='yellow', width=1, dash='dot')), row=1, col=1)
    
    if show_shifted_liq:
        fig.add_trace(go.Scatter(x=df_filtered['Date'], y=df_filtered['Shifted_Liquidity'], 
                      name="Shifted Liquidity", line=dict(color='mediumpurple', width=3)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df_filtered['Date'], y=df_filtered['SP500'], 
                  name="S&P 500", line=dict(color='darkorange', width=2)), row=1, col=1, secondary_y=True)

    if show_vix:
        fig.add_trace(go.Scatter(x=df_filtered['Date'], y=df_filtered['VIX'], 
                      name="VIX", line=dict(color='crimson', width=2), fill='tozeroy', 
                      fillcolor='rgba(220, 20, 60, 0.1)'), row=2, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
