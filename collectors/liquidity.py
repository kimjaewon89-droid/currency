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

    print("📊 [데이터 엔진] FRED 및 Market 데이터 수집 시작...")
    fred_key = os.environ.get('FRED_API_KEY')
    fred = Fred(api_key=fred_key)

    # 1. FRED 지표 정의
    fred_tickers = {
        'Total_Assets': 'WALCL', 
        'TGA': 'WDTGAL', 
        'Reverse_Repo': 'RRPONTSYD',
        'M2': 'M2SL',
        'HY_Spread': 'BAMLH0A0HYM2' 
    }
    
    fred_dfs = []
    for name, ticker in fred_tickers.items():
        try:
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(s, columns=[name])
            if name == 'M2':
                temp_df[name] = temp_df[name] * 1000 # 단위 보정
            temp_df.index = pd.to_datetime(temp_df.index).normalize()
            fred_dfs.append(temp_df)
            print(f"✅ {name} 수집 완료")
        except Exception as e:
            print(f"⚠️ {name} 수집 실패: {e}")

    # FRED 데이터 병합 (하나라도 성공했다면 진행)
    if not fred_dfs:
        return pd.DataFrame()
    
    liq_df = pd.concat(fred_dfs, axis=1)

    # 2. 시장 데이터 수집 (S&P500, VIX)
    try:
        mkt_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date, progress=False)
        # yfinance 최신 버전의 컬럼 구조 대응
        mkt_df = pd.DataFrame(index=mkt_raw.index)
        if ('Close', '^GSPC') in mkt_raw.columns: # Multi-index 대응
            mkt_df['SP500'] = mkt_raw[('Close', '^GSPC')]
            mkt_df['VIX'] = mkt_raw[('Close', '^VIX')]
        else:
            mkt_df['SP500'] = mkt_raw['Close']['^GSPC'] if 'Close' in mkt_raw.columns else mkt_raw['^GSPC']
            mkt_df['VIX'] = mkt_raw['Close']['^VIX'] if 'Close' in mkt_raw.columns else mkt_raw['^VIX']
            
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
        print("✅ 시장 데이터(S&P500, VIX) 수집 완료")
    except Exception as e:
        print(f"⚠️ 시장 데이터 수집 실패: {e}")
        mkt_df = pd.DataFrame()

    # 3. 최종 병합 및 전방/후방 채우기
    # 데이터가 비어있는 날짜(주말 등)를 ffill로 메워야 차트가 끊기지 않습니다.
    final_combined = liq_df.join(mkt_df, how='outer').ffill().bfill()
    
    # 디버깅: 컬럼이 제대로 들어갔는지 로그 출력
    print(f"📝 최종 데이터 컬럼 목록: {final_combined.columns.tolist()}")
    
    return final_combined
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
