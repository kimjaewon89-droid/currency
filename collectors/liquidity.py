import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

def get_liquidity_data(start_date, end_date):
    """연준 유동성 및 시장 기초 데이터를 수집하여 반환합니다."""
    # 1. FRED 데이터 수집
    try:
        fred = Fred(api_key=os.environ.get('FRED_API_KEY'))
        fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
        fred_dfs = []
        for name, ticker in fred_tickers.items():
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(s, columns=[name])
            df.index = pd.to_datetime(df.index).normalize()
            fred_dfs.append(df)
        liq_df = pd.concat(fred_dfs, axis=1)
    except Exception as e:
        print(f"FRED 에러: {e}")
        liq_df = pd.DataFrame()

    # 2. yfinance 데이터 수집
    try:
        sp = yf.download("^GSPC", start=start_date, end=end_date, progress=False)["Close"]
        vx = yf.download("^VIX", start=start_date, end=end_date, progress=False)["Close"]
        
        # Multi-index 대응
        sp_val = sp.iloc[:, 0] if len(sp.shape) > 1 else sp
        vx_val = vx.iloc[:, 0] if len(vx.shape) > 1 else vx
        
        mkt_df = pd.DataFrame({'SP500': sp_val, 'VIX': vx_val})
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
    except Exception as e:
        print(f"YFinance 에러: {e}")
        mkt_df = pd.DataFrame(columns=['SP500', 'VIX'])

    # 데이터 병합
    combined = liq_df.join(mkt_df, how='outer').ffill().bfill()
    return combined
