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
    st.title("🛡️ Captain's Multi-Layer Tactical Map")

    # 2. 유동성 시차 설정
    shift_days = st.sidebar.slider("유동성 시차(Shift) 설정 (일)", 0, 60, 21)
    # --- [본문 상단 컨트롤러 레이아웃] ---
    # 위젯들을 가로로 배치하기 위해 컬럼 생성
    ctrl_col1, ctrl_col2 = st.columns([2, 1])

    with ctrl_col1:
        # 1. 범위형 기간 설정 (본문 배치)
        min_date = df['Date'].min().to_pydatetime()
        max_date = df['Date'].max().to_pydatetime()
        
        selected_range = st.slider(
            "📅 조회 기간 범위 설정",
            min_value=min_date,
            max_value=max_date,
            value=(max_date - timedelta(days=365), max_date),
            format="YYYY-MM-DD",
            key="main_date_slider"
        )
        start_date, end_date = selected_range

    with ctrl_col2:
        # 2. 유동성 시차 설정 (본문 배치)
        shift_days = st.number_input(
            "⏳ 유동성 시차(Shift) 설정 (일)", 
            min_value=0, max_value=90, value=21, step=1,
            key="main_shift_input"
        )

    st.divider() # 시각적 구분을 위한 구분선

    # --- 사이드바: 향후 추가될 기능들을 위한 공간 ---
    st.sidebar.header("🕹️ 추가 전술 옵션")
    st.sidebar.info("여기에 추가 지표(M2, 신용 스프레드 등) 온/오프 기능을 넣을 예정입니다.")

    # --- 데이터 처리 ---
    # 선택된 날짜 범위로 데이터 필터링
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    df_filtered = df.loc[mask].copy()

    # [중요] 시차 적용은 전체 데이터에서 미리 해야 경계선 데이터가 끊기지 않습니다.
    # 전체 데이터 기준 시프트 후 필터링된 구간에 다시 매핑
    # 시차 적용 (전체 데이터 기준 선행 계산)
    df['Shifted_Liquidity'] = df['Net_Liquidity'].shift(shift_days)
    df_filtered = df.loc[mask].copy()

    st.title("🛡️ Captain's Multi-Layer Tactical Map")
    st.info(f"📅 **조회 기간:** {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} | ⏳ **시차:** {shift_days}일")

    # 2행 1열 서브플롯
    # --- 그래프 생성 ---
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.1,
        vertical_spacing=0.08,
        subplot_titles=("<b>[전술 1] 유동성 시차 투영 (Current vs Shifted)</b>", "<b>[전술 2] VIX 공포 지수</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # --- 상단 그래프 (행 1) ---
    # 원본 유동성 (노란색 점선 - Captain의 요청 컬러 반영)
    # 1. 원본 유동성 (노란색 점선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Net_Liquidity'], 
                   name="Raw Liquidity (Current)", 
                   line=dict(color='yellow', width=1, dash='dot')),
        row=1, col=1, secondary_y=False
    )

    # 시프트 유동성 (보라색 실선)
    # 2. 시프트 유동성 (보라색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['Shifted_Liquidity'], 
                   name=f"Liquidity (Shifted {shift_days}d)", 
                   line=dict(color='mediumpurple', width=3)),
        row=1, col=1, secondary_y=False
    )

    # S&P 500 (주황색 실선)
    # 3. S&P 500 (주황색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['SP500'], 
                   name="S&P 500 (Market)", 
                   line=dict(color='darkorange', width=2)),
        row=1, col=1, secondary_y=True
    )

    # --- 하단 그래프 (행 2) ---
    # 4. VIX 지수 (빨간색 실선)
    fig.add_trace(
        go.Scatter(x=df_filtered['Date'], y=df_filtered['VIX'], 
                   name="VIX (Fear Index)", 
@@ -97,16 +104,11 @@
        row=2, col=1
    )

    # --- 레이아웃 설정 ---
    fig.update_layout(
        height=850,
        height=800,
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    fig.update_yaxes(title_text="Liquidity ($M)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="S&P 500", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="VIX Index", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
