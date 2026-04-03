import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 1. 설정
FRED_API_KEY = os.environ.get('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    # 수집 기간 설정 (1년)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # --- Part A: FRED에서 연준 유동성 지표 수집 ---
    fred_tickers = {
        'Total_Assets': 'WALCL',
        'TGA': 'WDTGAL',
        'Reverse_Repo': 'RRPONTSYD'
    }
    
    fred_list = []
    for name, ticker in fred_tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            fred_list.append(pd.DataFrame(series, columns=[name]))
        except Exception as e:
            print(f"FRED Error ({name}): {e}")

    # --- Part B: yfinance에서 주가 및 VIX 수집 (신뢰도 100%) ---
    try:
        # ^GSPC: S&P 500 지수, ^VIX: 변동성 지수
        market_data = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date)['Adj Close']
        market_data.columns = ['SP500', 'VIX']
    except Exception as e:
        print(f"Yahoo Finance Error: {e}")
        market_data = pd.DataFrame()

    # --- Part C: 데이터 병합 ---
    if not fred_list:
        print("연준 데이터를 가져오지 못했습니다.")
        return

    liq_df = pd.concat(fred_list, axis=1)
    # 인덱스(날짜) 맞추기 위해 병합
    final_new_df = liq_df.join(market_data, how='left')
    final_new_df = final_new_df.ffill().dropna()
    final_new_df.index.name = 'Date'
    final_new_df = final_new_df.reset_index()

    # 필수 지표 확인 후 실질 유동성 계산
    required = ['Total_Assets', 'TGA', 'Reverse_Repo', 'SP500']
    if all(col in final_new_df.columns for col in required):
        final_new_df['Net_Liquidity'] = final_new_df['Total_Assets'] - (final_new_df['TGA'] + final_new_df['Reverse_Repo'])
    else:
        print(f"데이터 누락 발생: {final_new_df.columns}")
        return

    # DB 저장
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        final_df = pd.concat([old_df, final_new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        final_df = final_new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    print(f"✅ DB 업데이트 완료 ({len(final_df)}행)")

if __name__ == "__main__":
    fetch_and_update_db()
