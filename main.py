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
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)
    
    # --- Part A: FRED 데이터 (자산, TGA, 역레포) ---
    fred_tickers = {'Total_Assets': 'WALCL', 'TGA': 'WDTGAL', 'Reverse_Repo': 'RRPONTSYD'}
    fred_list = []
    
    for name, ticker in fred_tickers.items():
        try:
            series = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            df = pd.DataFrame(series, columns=[name])
            # 인덱스를 '날짜' 형식으로 강제 변환 및 시간 제거
            df.index = pd.to_datetime(df.index).normalize()
            fred_list.append(df)
        except Exception as e:
            print(f"FRED Error ({name}): {e}")

    if not fred_list: return

    # FRED 데이터 병합 (날짜 기준)
    liq_df = pd.concat(fred_list, axis=1)

    # --- Part B: yfinance 데이터 (S&P 500, VIX) ---
    # 최신 yfinance의 MultiIndex 문제를 피하기 위해 개별 추출 후 인덱스 재정렬
    market_data = pd.DataFrame(index=liq_df.index) # FRED 날짜 기준 틀 생성
    
    for symbol, col_name in [("^GSPC", "SP500"), ("^VIX", "VIX")]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            if not hist.empty:
                # 시간대 제거 및 날짜 정규화
                hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
                # 필요한 'Close' 가격만 추출하여 메인 틀에 합침
                market_data[col_name] = hist['Close']
        except Exception as e:
            print(f"YFinance Error ({symbol}): {e}")

    # --- Part C: 병합 및 빈칸 메우기 ---
    # FRED 데이터와 Market 데이터를 합치고, 주말/휴일 빈칸을 앞뒤 데이터로 철저히 메움
    final_new_df = liq_df.join(market_data, how='left')
    final_new_df = final_new_df.ffill().bfill() # 빈칸 방어막
    
    final_new_df.index.name = 'Date'
    final_new_df = final_new_df.reset_index()

    # 필수 컬럼 존재 여부 재확인
    if 'SP500' not in final_new_df.columns or final_new_df['SP500'].isnull().all():
        print("🚨 치명적 오류: S&P 500 데이터를 끝내 확보하지 못했습니다.")
        return

    # 실질 유동성 계산
    final_new_df['Net_Liquidity'] = final_new_df['Total_Assets'] - (final_new_df['TGA'] + final_new_df['Reverse_Repo'])

    # --- Part D: DB 저장 및 업데이트 ---
    db_path = 'liquidity_db.csv'
    if os.path.exists(db_path):
        old_df = pd.read_csv(db_path)
        old_df['Date'] = pd.to_datetime(old_df['Date'])
        # 중복 제거 시 '날짜' 기준으로 최신 데이터만 남김
        final_df = pd.concat([old_df, final_new_df]).drop_duplicates(subset=['Date'], keep='last')
    else:
        final_df = final_new_df
        
    final_df = final_df.sort_values('Date')
    final_df.to_csv(db_path, index=False)
    print(f"✅ DB 업데이트 성공! 현재 데이터 행 수: {len(final_df)}")

    # 텔레그램 알림 (옵션)
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if bot_token and chat_id and len(final_df) >= 2:
        import requests
        latest, prev = final_df.iloc[-1], final_df.iloc[-2]
        liq_change = latest['Net_Liquidity'] - prev['Net_Liquidity']
        if liq_change <= -50000 or latest['VIX'] >= 20:
            msg = f"🚨 [시장 경보]\n유동성 변동: ${liq_change:,.0f}M\nVIX: {latest['VIX']:,.2f}\nS&P500: {latest['SP500']:,.2f}"
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={'chat_id': chat_id, 'text': msg})

if __name__ == "__main__":
    fetch_and_update_db()
