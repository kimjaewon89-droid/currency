import os
import pandas as pd
from fredapi import Fred
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

FRED_API_KEY = os.environ.get('FRED_API_KEY')
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY가 설정되지 않았습니다. GitHub Secrets를 확인하세요.")
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    tickers = {
        'Total_Assets': 'WALCL',
        'TGA': 'WDTGAL',
        'Reverse_Repo': 'RRPONTSYD',
        'SP500': 'SP500',
        'VIX': 'VIXCLS'
    }
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=30)
    
    df_list = []
    for name, ticker in tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(series, columns=[name])
            df_list.append(temp_df)
        except Exception as e:
            print(f"Error fetching {ticker} ({name}): {e}")
    
    if not df_list:
        print("데이터를 전혀 가져오지 못했습니다. 종료합니다.")
        return

    new_df = pd.concat(df_list, axis=1)
    new_df.index.name = 'Date'
    new_df = new_df.reset_index()
    
    # 수정 1: Pandas 경고 메시지 해결 (ffill 직접 사용)
    new_df = new_df.ffill()
    new_df = new_df.dropna()
    
    # 수정 2: 필수 데이터 누락 시 계산을 멈추는 방어 로직 추가
    required_cols = ['Total_Assets', 'TGA', 'Reverse_Repo']
    missing_cols = [col for col in required_cols if col not in new_df.columns]
    
    if missing_cols:
        print(f"🚨 FRED 서버 문제로 필수 데이터를 가져오지 못했습니다: {missing_cols}")
        print("잘못된 계산을 막기 위해 오늘 DB 업데이트는 건너뜁니다.")
        return # 여기서 프로그램 안전 종료
    
    # 필수 데이터가 모두 있을 때만 유동성 계산
    new_df['Net_Liquidity'] = new_df['Total_Assets'] - (new_df['TGA'] + new_df['Reverse_Repo'])
    
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        final_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        final_df = new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    print(f"✅ DB 업데이트 완료. 총 데이터 수: {len(final_df)}행")
    
    plt.figure(figsize=(10, 5))
    plt.plot(final_df['Date'], final_df['Net_Liquidity'], color='blue')
    plt.title(f"Net Liquidity DB Updated: {datetime.now().strftime('%Y-%m-%d')}")
    plt.grid(True)
    plt.savefig('liquidity_chart.png')

if __name__ == "__main__":
    fetch_and_update_db()
