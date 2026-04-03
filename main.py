import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# 1. API 설정
FRED_API_KEY = os.environ.get('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # --- Part A: FRED 데이터 (자산, TGA, 역레포) ---
    print("FRED 데이터 수집 중...")
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_dfs = []
    
    for name, ticker in fred_tickers.items():
        series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
        df = pd.DataFrame(series, columns=[name])
        df.index = pd.to_datetime(df.index).normalize()
        fred_dfs.append(df)
    
    liq_df = pd.concat(fred_dfs, axis=1)

    # --- Part B: yfinance 데이터 (가장 안전한 개별 추출 방식) ---
    print("시장 데이터 수집 중...")
    # S&P 500
    sp500_raw = yf.download("^GSPC", start=start_date, end=end_date, progress=False)
    # VIX
    vix_raw = yf.download("^VIX", start=start_date, end=end_date, progress=False)

    # 핵심: 최신 yfinance의 복잡한 열 구조를 무시하고 값만 추출
    # 어떤 버전이든 'Close' 열의 데이터만 강제로 가져옵니다.
    sp500_series = sp500_raw['Close'].iloc[:, 0] if isinstance(sp500_raw['Close'], pd.DataFrame) else sp500_raw['Close']
    vix_series = vix_raw['Close'].iloc[:, 0] if isinstance(vix_raw['Close'], pd.DataFrame) else vix_raw['Close']

    market_data = pd.DataFrame({
        'SP500': sp500_series,
        'VIX': vix_series
    })
    
    # 시간대 제거 및 날짜 정규화
    market_data.index = pd.to_datetime(market_data.index).tz_localize(None).normalize()

    # --- Part C: 병합 및 저장 ---
    # FRED 날짜(기준)에 주가 데이터를 붙임
    final_df = liq_df.join(market_data, how='left')
    
    # 주말/공휴일 빈칸은 이전 값으로 채움
    final_df = final_df.ffill().bfill()
    
    # 실질 유동성 계산
    final_df['Net_Liquidity'] = final_df['Total_Assets'] - (final_df['TGA'] + final_df['Reverse_Repo'])
    
    final_df.index.name = 'Date'
    final_df = final_df.reset_index()

    # CSV 파일로 즉시 저장 (생성 보장)
    final_df.to_csv('liquidity_db.csv', index=False)
    print(f"✅ CSV 생성 성공! 총 {len(final_df)}행 데이터가 저장되었습니다.")
    print(final_df.tail(3))

if __name__ == "__main__":
    fetch_and_update_db()
