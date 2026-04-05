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

    # 1. FRED 데이터 (유동성 및 신용 경색 지표)
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
                temp_df[name] = temp_df[name] * 1000  # M2 스케일 보정 (기존 로직 유지)
            temp_df.index = pd.to_datetime(temp_df.index).normalize()
            fred_dfs.append(temp_df)
        except Exception as e:
            print(f"⚠️ {name} 수집 실패: {e}")

    if not fred_dfs:
        raise Exception("FRED 데이터를 수집하지 못했습니다.")

    liq_df = pd.concat(fred_dfs, axis=1)

    # 2. Yahoo Finance 데이터 (VIX 및 스마트 머니 분석용 ETF 추가)
    yf_mapping = {
        'SP500': '^GSPC',
        'VIX': '^VIX',
        'SPY': 'SPY',
        'TLT': 'TLT',
        'XLY': 'XLY',
        'XLP': 'XLP',
        'XLK': 'XLK',
        'XLU': 'XLU',
        'BRK-B': 'BRK-B'
    }

    tickers_to_download = list(yf_mapping.values())

    try:
        # 여러 종목을 한 번에 다운로드
        mkt_raw = yf.download(tickers_to_download, start=start_date, end=end_date, progress=False)

        # 다중 티커 다운로드 시 'Close' 컬럼 하위에 종목들이 위치함
        if 'Close' in mkt_raw.columns:
            price_df = mkt_raw['Close']
        else:
            price_df = mkt_raw

        mkt_df = pd.DataFrame(index=price_df.index)

        # 다운로드된 데이터에서 매핑된 이름으로 컬럼명 변경하여 mkt_df에 할당
        for name, ticker in yf_mapping.items():
            if ticker in price_df.columns:
                mkt_df[name] = price_df[ticker]

        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()

    except Exception as e:
        print(f"⚠️ Yahoo Finance 수집 실패: {e}")
        mkt_df = pd.DataFrame()

    # 3. 데이터 병합 및 빈칸 채우기
    final_combined = liq_df.join(mkt_df, how='outer').ffill().bfill()

    # 4. Net_Liquidity 계산 (기존 핵심 로직 유지) 및 저장
    if not final_combined.empty and 'Total_Assets' in final_combined.columns:
        final_combined['Net_Liquidity'] = final_combined['Total_Assets'] - (
                final_combined.get('TGA', 0) + final_combined.get('Reverse_Repo', 0))
        final_combined.index.name = 'Date'
        final_combined.reset_index().to_csv('liquidity_db.csv', index=False)
        print(f"✅ 데이터 업데이트 성공! (마지막 날짜: {final_combined.index.max().strftime('%Y-%m-%d')})")
        return True

    return False


if __name__ == "__main__":
    update_database()