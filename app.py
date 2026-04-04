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
@@ -24,23 +23,36 @@
    # --- 사이드바: 전술 제어판 ---
    st.sidebar.header("🕹️ 전술 제어판")

    # 1. 조회 기간 설정 (최근 n일)
    max_days = len(df) # 실제 데이터 개수만큼 제한
    view_days = st.sidebar.slider("조회 기간 설정 (최근 n일)", 90, 1095, 365)
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
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 45, 21)
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 60, 21)

    # --- 데이터 처리 ---
    # 선택한 기간만큼 데이터 자르기
    cutoff_date = df['Date'].max() - timedelta(days=view_days)
    df_filtered = df[df['Date'] >= cutoff_date].copy()
    # 선택된 날짜 범위로 데이터 필터링
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    df_filtered = df.loc[mask].copy()

    # 유동성 시차 적용 (필터링된 데이터 기반)
    df_filtered['Shifted_Liquidity'] = df_filtered['Net_Liquidity'].shift(shift_days)
    # [중요] 시차 적용은 전체 데이터에서 미리 해야 경계선 데이터가 끊기지 않습니다.
    # 전체 데이터 기준 시프트 후 필터링된 구간에 다시 매핑
    df['Shifted_Liquidity'] = df['Net_Liquidity'].shift(shift_days)
    df_filtered = df.loc[mask].copy()

    st.title("🛡️ Captain's Multi-Layer Tactical Map")
    st.info(f"현재 최근 **{view_days}일** 데이터를 조회 중이며, 유동성 시차는 **{shift_days}일**입니다.")
    st.info(f"📅 **조회 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} | ⏳ **시차:** {shift_days}일")

    # 2행 1열 서브플롯
    fig = make_subplots(
@@ -52,7 +64,7 @@
    )

    # --- 상단 그래프 (행 1) ---
    # 원본 유동성 (연한 파란색 점선)
    # 원본 유동성 (노란색 점선 - Captain의 요청 컬러 반영)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                   name="Raw Liquidity (Current)", 
@@ -77,7 +89,6 @@
    )

    # --- 하단 그래프 (행 2) ---
    # VIX 지수 (빨간색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['VIX'], 
                   name="VIX (Fear Index)", 
