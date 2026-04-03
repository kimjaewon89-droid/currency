import os
import pandas as pd
from fredapi import Fred
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 1. API 키 설정 (GitHub Secrets에서 환경변수로 불러옴)
FRED_API_KEY = os.environ.get('FRED_API_KEY')
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY가 설정되지 않았습니다. GitHub Secrets를 확인하세요.")
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    # 2. 수집할 지표 티커 설정 (S&P 500, VIX 추가)
    tickers = {
        'Total_Assets': 'WALCL',
        'TGA': 'WDTGAL',
        'Reverse_Repo': 'RRPONTSYD',
        'SP500': 'SP500',
        'VIX': 'VIXCLS'
    }
    
    # 3. 최근 30일 데이터 수집 (주기가 다른 데이터를 병합하기 위한 버퍼)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=30)
    
    df_list = []
    for name, ticker in tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(series, columns=[name])
            df_list.append(temp_df)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
    
    if not df_list:
        print("데이터를 가져오지 못했습니다.")
        return

    # 4. 데이터 병합 및 결측치 처리
    new_df = pd.concat(df_list, axis=1)
    new_df.index.name = 'Date'
    new_df = new_df.reset_index()
    
    # 주간 데이터(WALCL)의 빈 날짜를 이전 값으로 채움 (Forward Fill)
    new_df = new_df.fillna(method='ffill')
    new_df = new_df.dropna() # 채울 수 없는 초기 결측치 제거
    
    # 5. 실질 유동성(Net Liquidity) 계산
    new_df['Net_Liquidity'] = new_df['Total_Assets'] - (new_df['TGA'] + new_df['Reverse_Repo'])
    
    # 6. 기존 DB(CSV) 업데이트 로직
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        
        # 기존 데이터와 새 데이터를 병합 후, 날짜 기준으로 중복 제거 (최신 데이터 덮어쓰기)
        final_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        # 최초 실행 시 새로운 DB 생성
        final_df = new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    print(f"✅ DB 업데이트 완료. 총 데이터 수: {len(final_df)}행")
    
    # 7. 워크플로우 정상 작동 확인용 임시 차트 생성
    plt.figure(figsize=(10, 5))
    plt.plot(final_df['Date'], final_df['Net_Liquidity'], color='blue')
    plt.title(f"Net Liquidity DB Updated: {datetime.now().strftime('%Y-%m-%d')}")
    plt.grid(True)
    plt.savefig('liquidity_chart.png')

if __name__ == "__main__":
    fetch_and_update_db()
