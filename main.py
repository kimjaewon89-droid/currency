import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

FRED_API_KEY = os.environ.get('FRED_API_KEY')
fred = Fred(api_key=FRED_API_KEY)

def fetch_and_update_db():
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # --- Part A: FRED 데이터 (자정 기준) ---
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_list = []
    
    for name, ticker in fred_tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(series, columns=[name])
            # 핵심 수정 1: 모든 날짜를 자정(00:00:00) 기준으로 강제 통일
            df.index = pd.to_datetime(df.index).normalize() 
            fred_list.append(df)
        except Exception as e:
            print(f"FRED Error ({name}): {e}")

    if not fred_list:
        print("연준 데이터를 가져오지 못했습니다. 종료합니다.")
        return

    liq_df = pd.concat(fred_list, axis=1)
    liq_df = liq_df[~liq_df.index.duplicated(keep='last')] # 중복 날짜 제거

    # --- Part B: yfinance 데이터 (오후 4시 -> 자정 통일) ---
    try:
        # download 방식을 사용하여 가장 안정적으로 데이터를 가져옵니다.
        sp_data = yf.download("^GSPC", start=start_date, end=end_date)
        vix_data = yf.download("^VIX", start=start_date, end=end_date)
        
        # yfinance 최신 버전의 MultiIndex 열 구조 방어
        sp_close = sp_data['Close'].squeeze() if isinstance(sp_data.columns, pd.MultiIndex) else sp_data['Close']
        vix_close = vix_data['Close'].squeeze() if isinstance(vix_data.columns, pd.MultiIndex) else vix_data['Close']

        market_data = pd.DataFrame({
            'SP500': sp_close, 
            'VIX': vix_close
        })
        
        # 핵심 수정 2: 타임존과 시간을 모두 날려버리고 FRED와 똑같은 날짜 형태로 맞춤
        market_data.index = pd.to_datetime(market_data.index).tz_localize(None).normalize()
        market_data = market_data[~market_data.index.duplicated(keep='last')]
        
    except Exception as e:
        print(f"YFinance Error: {e}")
        market_data = pd.DataFrame(columns=['SP500', 'VIX'])

    # --- Part C: 완벽한 병합 (Outer Join) ---
    # 교집합이 아닌 합집합으로 묶어, 휴일/주말 누락을 방지합니다.
    final_new_df = liq_df.join(market_data, how='outer')
    final_new_df = final_new_df.ffill().bfill()
    final_new_df.index.name = 'Date'
    final_new_df = final_new_df.reset_index()

    required = ['Total_Assets', 'TGA', 'Reverse_Repo', 'SP500']
    missing = [col for col in required if col not in final_new_df.columns]
    
    if missing:
        print(f"🚨 데이터 누락 발생: {missing}")
        return

    final_new_df['Net_Liquidity'] = final_new_df['Total_Assets'] - (final_new_df['TGA'] + final_new_df['Reverse_Repo'])

    # --- Part D: DB 저장 ---
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        final_df = pd.concat([old_df, final_new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        final_df = final_new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    print(f"✅ DB 업데이트 완료! S&P 500 포함 데이터수: ({len(final_df)}행)")

    # 텔레그램 알림 기능
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if bot_token and chat_id and len(final_df) >= 2:
        import requests
        latest, prev = final_df.iloc[-1], final_df.iloc[-2]
        liq_change = latest['Net_Liquidity'] - prev['Net_Liquidity']
        if liq_change <= -50000 or latest['VIX'] >= 20:
            msg = f"🚨 [시장 경고]\n유동성 변동: ${liq_change:,.0f}M\nVIX: {latest['VIX']:,.2f}"
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={'chat_id': chat_id, 'text': msg})

if __name__ == "__main__":
    fetch_and_update_db()
