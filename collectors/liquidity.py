import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# --- [1. 데이터 수집 함수: main.py에서 사용] ---
def get_liquidity_data(start_date, end_date):
    print("📊 유동성 데이터 수집 중...")
    try:
        fred = Fred(api_key=os.environ.get('FRED_API_KEY'))
        # M2SL 추가 포함
        fred_tickers = {
            'Total_Assets': 'WALCL', 
            'TGA': 'WDTGAL', 
            'Reverse_Repo': 'RRPONTSYD',
            'M2': 'M2SL' 
        }
        
        fred_dfs = []
        for name, ticker in fred_tickers.items():
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(s, columns=[name])
            if name == 'M2':
                df[name] = df[name] * 1000 # 단위 보정
            df.index = pd.to_datetime(df.index).normalize()
            fred_dfs.append(df)
        liq_df = pd.concat(fred_dfs, axis=1)
        
        # 시장 데이터 수집
        sp = yf.download("^GSPC", start=start_date, end=end_date, progress=False)["Close"]
        vx = yf.download("^VIX", start=start_date, end=end_date, progress=False)["Close"]
        
        sp_val = sp.iloc[:, 0] if len(sp.shape) > 1 else sp
        vx_val = vx.iloc[:, 0] if len(vx.shape) > 1 else vx
        mkt_df = pd.DataFrame({'SP500': sp_val, 'VIX': vx_val})
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
        
        return liq_df.join(mkt_df, how='outer').ffill().bfill()
    except Exception as e:
        print(f"❌ 수집 에러: {e}")
        return pd.DataFrame()

# --- [2. UI 렌더링 함수: app.py에서 사용] ---
def render_screen(df):
    import streamlit as st  # <--- 함수 안으로 이동 (핵심!)
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.title("🛡️ Liquidity Tactical View")
    # ... (기존 render_screen 코드 동일)
