import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

FRED_API_KEY = os.environ.get('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # 1. FRED 데이터 수집
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_dfs = []
    for name, ticker in fred_tickers.items():
        series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
        df = pd.DataFrame(series, columns=[name])
        df.index = pd.to_datetime(df.index).normalize()
        fred_dfs.append(df)
    
    liq_df = pd.concat(fred_dfs, axis=1)

    # 2. yfinance 데이터 수집 (최신 Multi-index 대응)
    market_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date)
    
    # 데이터 구조 강제 정렬
    sp500 = market_raw['Close']['^GSPC'] if '^GSPC' in market_raw['Close'] else market_raw['Close']
    vix = market_raw['Close']['^VIX'] if '^VIX' in market_raw['Close'] else market_raw['Close']
    
    market_data = pd.DataFrame({'SP500': sp500, 'VIX': vix})
    market_data.index = pd.to_datetime(market_data.index).tz_localize(None).normalize()

    # 3. 병합 및 결측치 채우기
    final_df = liq_df.join(market_data, how='left').ffill().bfill()
    final_df['Net_Liquidity'] = final_df['Total_Assets'] - (final_df['TGA'] + final_df['Reverse_Repo'])
    final_df.index.name = 'Date'
    final_df = final_df.reset_index()

    # 4. 저장
    final_df.to_csv('liquidity_db.csv', index=False)
    print("✅ 새 DB 생성 완료!")
    print(final_df.tail(3))

if __name__ == "__main__":
    fetch_and_update_db()
