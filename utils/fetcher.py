import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일에서 API KEY 로드
load_dotenv()


def update_database():
    fred_key = os.environ.get('FRED_API_KEY')
    if not fred_key:
        raise ValueError("FRED_API_KEY가 설정되지 않았습니다.")

    fred = Fred(api_key=fred_key)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=3650)  # 10년

    fred_tickers = {
        'Total_Assets': 'WALCL',
        'TGA': 'WDTGAL',
        'Reverse_Repo': 'RRPONTSYD',
        'M2': 'M2SL',
        'HY_Spread': 'BAMLH0A0HYM2'
    }

    fred_dfs = []
    for name, ticker in fred_tickers.items():
        try:
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(s, columns=[name])
            if name == 'M2':
                temp_df[name] = temp_df[name] * 1000
            temp_df.index = pd.to_datetime(temp_df.index).normalize()
            fred_dfs.append(temp_df)
        except Exception as e:
            print(f"⚠️ {name} 수집 실패: {e}")

    if not fred_dfs:
        raise Exception("FRED 데이터를 수집하지 못했습니다.")

    liq_df = pd.concat(fred_dfs, axis=1)

    try:
        mkt_raw = yf.download(["^GSPC", "^VIX"], start=start_date, end=end_date, progress=False)
        mkt_df = pd.DataFrame(index=mkt_raw.index)
        if ('Close', '^GSPC') in mkt_raw.columns:
            mkt_df['SP500'] = mkt_raw[('Close', '^GSPC')]
            mkt_df['VIX'] = mkt_raw[('Close', '^VIX')]
        else:
            mkt_df['SP500'] = mkt_raw['Close']['^GSPC'] if 'Close' in mkt_raw.columns else mkt_raw['^GSPC']
            mkt_df['VIX'] = mkt_raw['Close']['^VIX'] if 'Close' in mkt_raw.columns else mkt_raw['^VIX']
        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()
    except Exception as e:
        mkt_df = pd.DataFrame()

    final_combined = liq_df.join(mkt_df, how='outer').ffill().bfill()

    # 필수 데이터 확인 후 Net_Liquidity 계산 및 저장
    if not final_combined.empty and 'Total_Assets' in final_combined.columns:
        final_combined['Net_Liquidity'] = final_combined['Total_Assets'] - (
                    final_combined.get('TGA', 0) + final_combined.get('Reverse_Repo', 0))
        final_combined.index.name = 'Date'
        final_combined.reset_index().to_csv('liquidity_db.csv', index=False)
        return True
    return False