import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# 1. 설정
FRED_API_KEY = os.environ.get('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # --- Part A: FRED 데이터 (자산, TGA, 역레포) ---
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_dfs = []
    
    for name, ticker in fred_tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(series, columns=[name])
            df.index = pd.to_datetime(df.index).normalize()
            fred_dfs.append(df)
        except Exception as e:
            print(f"FRED Error ({name}): {e}")

    if not fred_dfs: return
    liq_df = pd.concat(fred_dfs, axis=1)

    # --- Part B: yfinance 데이터 (가장 확실한 download 방식) ---
    try:
        # 두 지수를 한 번에 다운로드
        market_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date)
        
        # 최신 yfinance의 Multi-index 구조를 단일 평면 구조로 강제 변환
        if isinstance(market_raw.columns, pd.MultiIndex):
            # 'Close' 레벨에서 각 티커별 데이터를 추출
            sp500_series = market_raw['Close']['^GSPC']
            vix_series = market_raw['Close']['^VIX']
        else:
            sp500_series = market_raw['Close'] # 단일 티커일 경우
            vix_series = pd.Series() # (이 경우는 발생하지 않음)

        market_data = pd.DataFrame({
            'SP500': sp500_series,
            'VIX': vix_series
        })
        
        # 시간대 제거 및 날짜 정규화 (FRED와 매칭)
        market_data.index = pd.to_datetime(market_data.index).tz_localize(None).normalize()
        
    except Exception as e:
        print(f"YFinance Critical Error: {e}")
        market_data = pd.DataFrame(columns=['SP500', 'VIX'])

    # --- Part C: 병합 및 빈칸 메우기 (핵심) ---
    # FRED 날짜 기준으로 합치되, 주식 시장이 닫힌 날(주말/휴일)은 이전 주가로 채움
    final_new_df = liq_df.join(market_data, how='left')
    final_new_df = final_new_df.ffill().bfill() 
    
    final_new_df.index.name = 'Date'
    final_new_df = final_new_df.reset_index()

    # 실질 유동성 계산
    if 'Total_Assets' in final_new_df.columns and 'TGA' in final_new_df.columns:
        final_new_df['Net_Liquidity'] = final_new_df['Total_Assets'] - (final_new_df['TGA'] + final_new_df['Reverse_Repo'])

    # --- Part D: DB 저장 및 업데이트 ---
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        # 중복 제거 (날짜 기준 최신행 유지)
        final_df = pd.concat([old_df, final_new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        final_df = final_new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    
    # 데이터 확인용 로그 (GitHub Actions 로그에서 확인 가능)
    print("--- 최종 수집 데이터 샘플 ---")
    print(final_df[['Date', 'Net_Liquidity', 'SP500', 'VIX']].tail(5))
    print(f"✅ 업데이트 완료: 총 {len(final_df)}행")

if __name__ == "__main__":
    fetch_and_update_db()
