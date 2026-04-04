import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# --- [1. 데이터 수집 함수: main.py에서 사용] ---
def get_liquidity_data(start_date, end_date):
    import os
    import pandas as pd
    from fredapi import Fred
    import yfinance as yf

    print("📊 데이터 수집 엔진 가동 중...")
    
    # 빈 데이터프레임 미리 생성 (에러 시 반환용)
    empty_df = pd.DataFrame()

    try:
        fred_key = os.environ.get('FRED_API_KEY')
        if not fred_key:
            print("❌ 에러: FRED_API_KEY가 설정되지 않았습니다.")
            return empty_df

        fred = Fred(api_key=fred_key)
        fred_tickers = {
            'Total_Assets': 'WALCL', 
            'TGA': 'WDTGAL', 
            'Reverse_Repo': 'RRPONTSYD',
            'M2': 'M2SL',
            'HY_Spread': 'BAMLH0A0HYM2' # 신용 지표 추가
        }
        
        fred_dfs = []
        for name, ticker in fred_tickers.items():
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(s, columns=[name])
            if name == 'M2':
                temp_df[name] = temp_df[name] * 1000
            temp_df.index = pd.to_datetime(temp_df.index).normalize()
            fred_dfs.append(temp_df)
        
        liq_df = pd.concat(fred_dfs, axis=1)

        # 시장 데이터 수집
        mkt_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date, progress=False)["Close"]
        
        # yfinance 데이터 구조 대응 (Multi-index 등)
        mkt_df = pd.DataFrame(index=mkt_raw.index)
        mkt_df['SP500'] = mkt_raw['^GSPC']
        mkt_df['VIX'] = mkt_raw['^VIX']
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
        
        # 최종 병합
        final_combined = liq_df.join(mkt_df, how='outer').ffill().bfill()
        return final_combined

    except Exception as e:
        print(f"❌ 데이터 수집 중 치명적 에러 발생: {e}")
        return empty_df # None이 아닌 빈 데이터프레임 반환
# --- [2. UI 렌더링 함수: app.py에서 사용] ---
# --- [상단은 데이터 수집 로직 (기존과 동일)] ---
import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

def get_liquidity_data(start_date, end_date):
    # (Captain이 사용 중인 기존 수집 로직 유지...)
    pass

# --- [하단 UI 로직: 이 부분을 정확히 채워주세요] ---
def render_screen(df):
    import streamlit as st  # 함수 내부 임포트로 Actions 에러 방지
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.title("🛡️ Liquidity Tactical View")
    
    # 1. 본문 상단 컨트롤러
    col1, col2 = st.columns([2, 1])
    with col1:
        # 데이터 기반 기본 날짜 설정
        max_dt = df['Date'].max().to_pydatetime()
        min_dt = df['Date'].min().to_pydatetime()
        start_def = max_dt - timedelta(days=365)
        
        selected_range = st.slider("📅 기간 설정", 
                                   min_dt, max_dt,
                                   (start_def, max_dt), 
                                   format="YYYY-MM-DD")
    with col2:
        shift = st.number_input("⏳ 유동성 시차(일)", 0, 90, 21)

    # 2. 데이터 필터링 및 시차 적용
    mask = (df['Date'] >= selected_range[0]) & (df['Date'] <= selected_range[1])
    df_plot = df.copy()
    
    # Net_Liquidity 컬럼 확인 후 시차 적용
    if 'Net_Liquidity' in df_plot.columns:
        df_plot['Shifted'] = df_plot['Net_Liquidity'].shift(shift)
    else:
        st.warning("Net_Liquidity 데이터를 찾을 수 없습니다.")
        return

    df_final = df_plot.loc[mask]

    # 3. 그래프 생성
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])
    
    # 상단: 유동성 vs 주가
    fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['Net_Liquidity'], 
                             name="Raw Liq", line=dict(color='yellow', width=1, dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['Shifted'], 
                             name="Shifted Liq", line=dict(color='mediumpurple', width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['SP500'], 
                             name="S&P 500", line=dict(color='darkorange', width=2)), row=1, col=1, secondary_y=True)
    
    # 하단: VIX
    if 'VIX' in df_final.columns:
        fig.add_trace(go.Scatter(x=df_final['Date'], y=df_final['VIX'], 
                                 name="VIX", fill='tozeroy', line=dict(color='crimson')), row=2, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    st.plotly_chart(fig, use_container_width=True)
