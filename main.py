import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

def fetch_and_update_db():
    print("🚀 프로세스 시작...")
    end_date = datetime.today()
    start_date = end_date - timedelta(days=1095) # 3년치로 확장
    
    # yfinance 호출 시 데이터 누락 방지를 위해 interval 설정 확인
    # (일일 데이터이므로 기본값으로 충분하지만, 3년치라면 데이터 양이 꽤 됩니다.)
    market_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date, progress=False)
        
    # 1. FRED 데이터 (실패 시 빈 데이터프레임 생성)
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

    # 2. yfinance 데이터 (가장 원시적인 방식)
    try:
        # 단일 티커로 각각 따로 가져와서 충돌 방지
        sp = yf.download("^GSPC", start=start_date, end=end_date, progress=False)["Close"]
        vx = yf.download("^VIX", start=start_date, end=end_date, progress=False)["Close"]
        
        # 데이터가 Series면 DataFrame으로 변환, DataFrame이면 첫 열 선택
        sp_val = sp.iloc[:, 0] if len(sp.shape) > 1 else sp
        vx_val = vx.iloc[:, 0] if len(vx.shape) > 1 else vx
        
        mkt_df = pd.DataFrame({'SP500': sp_val, 'VIX': vx_val})
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
    except Exception as e:
        print(f"YFinance 에러: {e}")
        mkt_df = pd.DataFrame(columns=['SP500', 'VIX'])

    # 3. 강제 병합 및 저장 (데이터가 없어도 파일은 만든다)
    final_df = liq_df.join(mkt_df, how='outer').ffill().bfill()
    
    if not final_df.empty:
        if 'Total_Assets' in final_df.columns:
            final_df['Net_Liquidity'] = final_df['Total_Assets'] - (final_df.get('TGA', 0) + final_df.get('Reverse_Repo', 0))
        final_df.index.name = 'Date'
        final_df = final_df.reset_index()
    
    # 이 명령어가 실행되면 파일은 무조건 생깁니다.
    final_df.to_csv('liquidity_db.csv', index=False)
    print(f"✅ 작업 완료! 파일 생성 여부: {os.path.exists('liquidity_db.csv')}")

if __name__ == "__main__":
    fetch_and_update_db()
