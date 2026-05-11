import os
import pandas as pd
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def update_database():
    fred_key = os.environ.get('FRED_API_KEY')
    if not fred_key:
        raise ValueError("FRED_API_KEY가 설정되지 않았습니다.")

    fred = Fred(api_key=fred_key)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=3650)  # 10년

    # 1. FRED 데이터
    fred_tickers = {
        'Total_Assets':  'WALCL',           # 연준 총자산 (백만달러)
        'TGA':           'WDTGAL',           # 재무부 일반계정
        'Reverse_Repo':  'RRPONTSYD',        # 역레포
        'M2':            'M2SL',             # M2 통화량 (10억달러 → 비교용 그대로 저장)
        'HY_Spread':     'BAMLH0A0HYM2',     # 하이일드 스프레드
        'Yield_Curve':   'T10Y2Y',           # 10Y-2Y 수익률 곡선 (음수 = 역전)
        'Fed_Rate':      'FEDFUNDS',          # 연방기금금리
        'Unemployment':  'UNRATE',            # 실업률
        'Oil_WTI':       'DCOILWTICO',        # WTI 원유 가격
    }

    fred_dfs = []
    for name, ticker in fred_tickers.items():
        try:
            s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
            temp_df = pd.DataFrame(s, columns=[name])
            temp_df.index = pd.to_datetime(temp_df.index).normalize()
            # FRED 주간/월간 데이터를 일간으로 리샘플링 (명시적 forward fill)
            temp_df = temp_df.resample('D').ffill()
            fred_dfs.append(temp_df)
        except Exception as e:
            print(f"⚠️ {name} ({ticker}) 수집 실패: {e}")

    if not fred_dfs:
        raise Exception("FRED 데이터를 수집하지 못했습니다.")

    liq_df = pd.concat(fred_dfs, axis=1)

    # 2. Yahoo Finance 데이터
    yf_mapping = {
        'SP500':  '^GSPC',
        'VIX':    '^VIX',
        'SPY':    'SPY',
        'TLT':    'TLT',
        'XLY':    'XLY',
        'XLP':    'XLP',
        'XLK':    'XLK',
        'XLU':    'XLU',
        'BRK-B':  'BRK-B',
        'GLD':    'GLD',    # 금 ETF (공포 헤지 / 안전자산 수요)
        'IWM':    'IWM',    # 러셀2000 소형주 (리스크온 감지)
        'QQQ':    'QQQ',    # 나스닥100 성장주 (성장 vs 가치 사이클)
    }

    tickers_to_download = list(yf_mapping.values())

    try:
        mkt_raw = yf.download(tickers_to_download, start=start_date, end=end_date, progress=False)

        if 'Close' in mkt_raw.columns:
            price_df = mkt_raw['Close']
        else:
            price_df = mkt_raw

        mkt_df = pd.DataFrame(index=price_df.index)

        for name, ticker in yf_mapping.items():
            if ticker in price_df.columns:
                mkt_df[name] = price_df[ticker]

        mkt_df.index = pd.to_datetime(mkt_df.index).tz_localize(None).normalize()

    except Exception as e:
        print(f"⚠️ Yahoo Finance 수집 실패: {e}")
        mkt_df = pd.DataFrame()

    # 3. 데이터 병합
    # FRED는 이미 일간 리샘플링 완료, 가격 데이터와 outer join 후 ffill
    final_combined = liq_df.join(mkt_df, how='outer')

    # 가격 컬럼은 ffill만 (bfill 사용 안 함 — 미래 데이터 역방향 채움 방지)
    price_cols = list(yf_mapping.keys())
    macro_cols = list(fred_tickers.keys())

    final_combined[macro_cols] = final_combined[macro_cols].ffill()
    final_combined[price_cols] = final_combined[price_cols].ffill()

    # 4. 파생 지표 계산
    if not final_combined.empty and 'Total_Assets' in final_combined.columns:
        final_combined['Net_Liquidity'] = final_combined['Total_Assets'] - (
            final_combined.get('TGA', 0) + final_combined.get('Reverse_Repo', 0))

        # 수익률 곡선 역전 여부 (bool)
        if 'Yield_Curve' in final_combined.columns:
            final_combined['Yield_Inverted'] = final_combined['Yield_Curve'] < 0

        final_combined.index.name = 'Date'
        final_combined.reset_index().to_csv('liquidity_db.csv', index=False)
        print(f"✅ 데이터 업데이트 성공! (마지막 날짜: {final_combined.index.max().strftime('%Y-%m-%d')})")
        return True

    return False


if __name__ == "__main__":
    update_database()
