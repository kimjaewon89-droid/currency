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
    
    # --- Part A: 연준 유동성 데이터 (FRED) ---
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_list = []
    
    for name, ticker in fred_tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(series, columns=[name])
            # 시간대(Timezone) 제거하여 기준 통일
            df.index = pd.to_datetime(df.index).tz_localize(None) 
            fred_list.append(df)
        except Exception as e:
            print(f"FRED Error ({name}): {e}")

    if not fred_list:
        print("연준 데이터를 가져오지 못했습니다. 종료합니다.")
        return

    liq_df = pd.concat(fred_list, axis=1)

    # --- Part B: 주가 및 VIX 데이터 (yfinance 개선판) ---
    try:
        # yfinance의 최신 Ticker 객체를 사용하여 안전하게 수집
        sp_data = yf.Ticker("^GSPC").history(start=start_date, end=end_date)
        vix_data = yf.Ticker("^VIX").history(start=start_date, end=end_date)
        
        market_data = pd.DataFrame({
            'SP500': sp_data['Close'], 
            'VIX': vix_data['Close']
        })
        market_data.index = market_data.index.tz_localize(None)
    except Exception as e:
        print(f"YFinance Error: {e}")
        market_data = pd.DataFrame(columns=['SP500', 'VIX'])

    # --- Part C: 병합 및 결측치(빈칸) 철통 방어 ---
    final_new_df = liq_df.join(market_data, how='left')
    
    # 주말 빈칸은 금요일 값으로(ffill), 1년 전 첫날 빈칸은 월요일 값으로(bfill) 채움
    final_new_df = final_new_df.ffill().bfill()
    final_new_df.index.name = 'Date'
    final_new_df = final_new_df.reset_index()

    required = ['Total_Assets', 'TGA', 'Reverse_Repo', 'SP500']
    missing = [col for col in required if col not in final_new_df.columns]
    
    if missing:
        print(f"🚨 필수 데이터 누락으로 인한 계산 중단: {missing}")
        return

    # 실질 유동성 최종 계산
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
    print(f"✅ DB 업데이트 완벽 성공! ({len(final_df)}행)")

    # 텔레그램 알림 로직 (기존 설정 유지)
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
