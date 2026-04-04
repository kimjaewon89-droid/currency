import pandas as pd
from datetime import timedelta

def render_screen(df):
    import streamlit as st
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.title("🚨 Credit Risk: High Yield Spread")
    st.info("""
    **하이일드 스프레드**는 부실 기업의 채권 금리와 국채 금리의 차이입니다. 
    이 수치가 급격히 오르면 시장의 '약한 고리'부터 무너지고 있다는 뜻이며, **VIX 폭발의 강력한 선행 신호**가 됩니다.
    """)

    if 'HY_Spread' not in df.columns:
        st.error("데이터셋에 HY_Spread 지표가 없습니다. main.py를 실행하여 데이터를 먼저 수집하세요.")
        return

    # 1. 컨트롤러
    max_dt = df['Date'].max().to_pydatetime()
    start_def = max_dt - timedelta(days=730) # 2년 기본
    selected_range = st.slider("조회 기간", df['Date'].min().to_pydatetime(), max_dt,
                               (start_def, max_dt), format="YYYY-MM-DD")
    
    df_plot = df[(df['Date'] >= selected_range[0]) & (df['Date'] <= selected_range[1])].copy()

    # 2. 그래프 생성 (상단: 스프레드 vs S&P500, 하단: 스프레드 vs VIX)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("<b>신용 위험(Spread) vs 주가(S&P 500)</b>", "<b>신용 위험(Spread) vs 공포(VIX)</b>"),
                        specs=[[{"secondary_y": True}], [{"secondary_y": True}]])

    # [상단] HY Spread (Red Line) & S&P500 (Orange Line)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['HY_Spread'], 
                             name="HY Spread", line=dict(color='crimson', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
                             name="S&P 500", line=dict(color='darkorange', width=1.5)), row=1, col=1, secondary_y=True)

    # [하단] HY Spread (Red Line) & VIX (Purple Area)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['HY_Spread'], 
                             name="HY Spread (Ref)", line=dict(color='crimson', width=1, dash='dot')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
                             name="VIX Index", fill='tozeroy', line=dict(color='mediumpurple')), row=2, col=1, secondary_y=True)

    # 위험 임계선 (과거 평균 약 4.5%~5% 구간을 위험 경계로 봅니다)
    fig.add_hline(y=4.5, line_dash="dash", line_color="yellow", annotation_text="Caution (4.5%)", row=1, col=1)
    fig.add_hline(y=6.0, line_dash="dash", line_color="red", annotation_text="DANGER (6.0%)", row=1, col=1)

    fig.update_layout(height=850, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
