import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

def render_screen(df):
    st.title("💵 M2 Money Supply Analysis")
    st.info("M2 통화량은 시중에 풀린 실물 화폐의 총량으로, 경기 침체와 물가를 예측하는 핵심 지표입니다.")

    if 'M2' not in df.columns:
        st.error("데이터셋에 M2 지표가 없습니다. main.py를 실행하여 데이터를 먼저 수집하세요.")
        return

    # 1. 데이터 가공: YoY(전년 대비 증감률) 계산
    df_m2 = df[['Date', 'M2', 'SP500']].copy()
    # 365일 전 데이터와 비교하여 증감률 계산
    df_m2['M2_YoY'] = df_m2['M2'].pct_change(periods=365) * 100

    # 2. 컨트롤러
    start_def = df['Date'].max().to_pydatetime() - timedelta(days=1095) # 3년 기본
    selected_range = st.slider("조회 기간", df['Date'].min().to_pydatetime(), df['Date'].max().to_pydatetime(),
                               (start_def, df['Date'].max().to_pydatetime()), format="YYYY-MM-DD")
    
    df_plot = df_m2[(df_m2['Date'] >= selected_range[0]) & (df_m2['Date'] <= selected_range[1])]

    # 3. 그래프 생성 (상단: M2 절대값 & 주가, 하단: M2 YoY%)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("<b>M2 통화량 vs S&P 500</b>", "<b>M2 전년 대비 증감률 (YoY %)</b>"),
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])

    # 상단: M2 (Green) & S&P500 (Orange)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['M2'], name="M2 Supply", line=dict(color='limegreen', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], name="S&P 500", line=dict(color='darkorange', width=1.5)), row=1, col=1, secondary_y=True)

    # 하단: M2 YoY (영역 차트)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['M2_YoY'], name="M2 YoY %", 
                             fill='tozeroy', line=dict(color='cyan', width=2)), row=2, col=1)
    # 0선 표시 (기준선)
    fig.add_hline(y=0, line_dash="dash", line_color="white", row=2, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
