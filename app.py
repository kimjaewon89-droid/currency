
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 페이지 기본 설정
st.set_page_config(page_title="Captain's Liquidity Radar", layout="wide")
st.title("🎯 연준 실질 유동성 전술 대시보드")

# 2. 데이터 로드
@st.cache_data(ttl=3600) # 1시간 동안 데이터 캐싱 (속도 향상)
def load_data():
    try:
        df = pd.read_csv('liquidity_db.csv')
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        df['Net_Liq_Change'] = df['Net_Liquidity'].diff()
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("데이터베이스(liquidity_db.csv)가 아직 생성되지 않았습니다. GitHub Actions가 실행될 때까지 기다려주세요.")
else:
    # --- 상단 요약 지표 (Metrics) ---
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    st.markdown("### 📊 Today's Liquidity Snapshot")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("순 유동성", f"${latest['Net_Liquidity']:,.0f}M", f"{latest['Net_Liquidity'] - prev['Net_Liquidity']:,.0f}M")
    col2.metric("S&P 500", f"{latest['SP500']:,.2f}", f"{latest['SP500'] - prev['SP500']:,.2f}")
    col3.metric("역레포(RRP)", f"${latest['Reverse_Repo']:,.0f}M", f"{latest['Reverse_Repo'] - prev['Reverse_Repo']:,.0f}M", delta_color="inverse")
    col4.metric("VIX (공포지수)", f"{latest['VIX']:,.2f}", f"{latest['VIX'] - prev['VIX']:,.2f}", delta_color="inverse")
    
    st.divider()

    # --- 차트 1: 실질 유동성 vs S&P 500 ---
    st.subheader("1. 유동성-증시 동기화 추적")
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig1.add_trace(go.Scatter(x=df['Date'], y=df['Net_Liquidity'], name="Net Liquidity", line=dict(color='blue', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df['Date'], y=df['SP500'], name="S&P 500", line=dict(color='orange', width=2)), secondary_y=True)
    
    fig1.update_layout(height=400, hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    fig1.update_yaxes(title_text="Net Liquidity ($ Mil)", secondary_y=False)
    fig1.update_yaxes(title_text="S&P 500 Index", secondary_y=True)
    st.plotly_chart(fig1, use_container_width=True)

    # --- 차트 2: VIX와 유동성 모멘텀 (위험 감지) ---
    st.subheader("2. 유동성 증감률과 VIX (Risk Radar)")
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    
    colors = ['blue' if val >= 0 else 'red' for val in df['Net_Liq_Change']]
    fig2.add_trace(go.Bar(x=df['Date'], y=df['Net_Liq_Change'], marker_color=colors, name='Liquidity Change'), secondary_y=False)
    fig2.add_trace(go.Scatter(x=df['Date'], y=df['VIX'], name="VIX", line=dict(color='purple', width=2)), secondary_y=True)
    
    fig2.update_layout(height=350, hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    fig2.update_yaxes(title_text="Liquidity Change", secondary_y=False)
    fig2.update_yaxes(title_text="VIX Index", secondary_y=True)
    st.plotly_chart(fig2, use_container_width=True)

    # --- 차트 3: 유동성 흡수/방출 컴포넌트 ---
    st.subheader("3. TGA & 역레포 (Liquidity Drainers)")
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=df['Date'], y=df['TGA'], mode='lines', name='TGA (재무부 금고)', stackgroup='one', fillcolor='rgba(255, 0, 0, 0.5)', line=dict(color='red')))
    fig3.add_trace(go.Scatter(x=df['Date'], y=df['Reverse_Repo'], mode='lines', name='역레포 (연준 금고)', stackgroup='one', fillcolor='rgba(0, 128, 0, 0.5)', line=dict(color='green')))
    
    fig3.update_layout(height=300, yaxis_title="Absorbed Amount ($ Mil)", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig3, use_container_width=True)
