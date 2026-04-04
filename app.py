import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="Captain's Strategic Command", layout="wide")

# --- [전술 지휘소: 화면 전환 로직] ---
def get_available_screens():
    """collectors 폴더의 파일들을 개별 화면 메뉴로 변환합니다."""
    folder = 'collectors'
    if not os.path.exists(folder):
        return ["Home"]
    files = [f[:-3] for f in os.listdir(folder) if f.endswith('.py') and f != '__init__.py']
    return ["Home"] + [f.capitalize() for f in files]

# 1. 사이드바 메뉴 (라디오 버튼으로 하나만 선택)
st.sidebar.header("📡 전술 화면 선택")
screens = get_available_screens()
selected_screen = st.sidebar.radio("이동할 분석 화면", screens)

# 2. 공통 데이터 로드 (필요시 각 화면에서 개별 로드 가능)
@st.cache_data(ttl=3600)
def load_base_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        return df.sort_values('Date')
    except:
        return pd.DataFrame()

df = load_data = load_base_data()

# --- [화면 분기 처리] ---

if selected_screen == "Home":
    st.title("🚀 Captain's Strategic Hub")
    st.write("사이드바에서 분석하려는 전술 화면을 선택하십시오.")
    st.info("현재 수집된 데이터 범위: " + str(df['Date'].min().date()) + " ~ " + str(df['Date'].max().date()))

elif selected_screen == "Liquidity":
    st.title("🛡️ Liquidity Tactical View")
    
    # [Liquidity 전용 컨트롤러]
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_range = st.slider("기간 설정", df['Date'].min().to_pydatetime(), df['Date'].max().to_pydatetime(),
                                   (df['Date'].max().to_pydatetime() - timedelta(days=365), df['Date'].max().to_pydatetime()))
    with col2:
        shift = st.number_input("유동성 시차(일)", 0, 90, 21)

    # [Liquidity 전용 그래프 로직]
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    mask = (df['Date'] >= selected_range[0]) & (df['Date'] <= selected_range[1])
    df_plot = df.loc[mask].copy()
    df_plot['Shifted'] = df['Net_Liquidity'].shift(shift)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, specs=[[{"secondary_y": True}], [{"secondary_y": False}]])
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], name="Raw", line=dict(color='yellow', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Shifted'], name="Shifted", line=dict(color='mediumpurple', width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], name="S&P500", line=dict(color='darkorange')), row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], name="VIX", fill='tozeroy', color='crimson'), row=2, col=1)
    
    fig.update_layout(height=800, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

elif selected_screen == "M2":
    st.title("💵 M2 Money Supply Analysis")
    st.warning("M2 분석 화면입니다. 여기에 M2.py 전용 로직을 구현하면 됩니다.")
    # M2 관련 별도 그래프 및 데이터 표 출력...

# --- [미래 확장] ---
# 새로운 파일(예: Credit.py)이 생기면 'elif selected_screen == "Credit":' 블록만 추가하면 끝!
