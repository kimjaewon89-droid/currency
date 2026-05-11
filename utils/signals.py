"""
모든 대시보드 지표를 단일 딕셔너리로 수집하는 모듈.
각 페이지(2~6)의 계산 로직을 그대로 재현.
"""
import pandas as pd
import numpy as np


def _safe(val, default=None):
    """NaN/None을 안전하게 처리"""
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


def collect_all_signals(df: pd.DataFrame) -> dict:
    """
    liquidity_db.csv 를 DataFrame으로 받아 모든 신호를 계산 후 dict 반환.
    각 값은 JSON 직렬화 가능한 Python 기본 타입.
    """
    df = df.copy().sort_values('Date').reset_index(drop=True)
    latest = df.iloc[-1]
    date_str = latest['Date'].strftime('%Y-%m-%d') if hasattr(latest['Date'], 'strftime') else str(latest['Date'])

    # ── 공통 지표 ──────────────────────────────────────────────────────
    sp500 = float(_safe(latest.get('SP500'), 0))
    vix   = float(_safe(latest.get('VIX'),   20))

    df['SMA_50']  = df['SP500'].rolling(50).mean()
    df['SMA_200'] = df['SP500'].rolling(200).mean()
    sma_50  = float(_safe(df['SMA_50'].iloc[-1],  sp500))
    sma_200 = float(_safe(df['SMA_200'].iloc[-1], sp500))

    # ── 1. 시장 레짐 ───────────────────────────────────────────────────
    if sma_50 > sma_200 and vix < 25:
        regime = 'BULL'
    elif sma_50 < sma_200 or vix > 30:
        regime = 'BEAR'
    else:
        regime = 'TRANSITION'

    yield_curve = float(_safe(latest.get('Yield_Curve'), 0))
    yield_inverted = bool(yield_curve < 0)
    if 'Yield_Curve' in df.columns:
        inv_streak = int((df['Yield_Curve'] < 0).iloc[::-1].cumprod().sum())
    else:
        inv_streak = 0

    # ── 2. 추세 지표 (2_Market_Timing) ────────────────────────────────
    delta = df['SP500'].diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss  = -1 * delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))

    df['MACD']        = df['SP500'].ewm(span=12, adjust=False).mean() - df['SP500'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    rsi_min = df['RSI'].rolling(14).min()
    rsi_max = df['RSI'].rolling(14).max()
    stoch_k = (df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9) * 100
    df['StochRSI_K'] = stoch_k.rolling(3).mean()

    recent5 = df.tail(5)
    rsi_val = float(_safe(df['RSI'].iloc[-1], 50))

    ma_golden_cross = bool(
        (recent5['SMA_50'] > recent5['SMA_200']).any() and
        (recent5['SMA_50'].shift(1) <= recent5['SMA_200'].shift(1)).any() and
        sp500 > sma_200
    )
    rsi_signal = bool(((recent5['RSI'] > 30) & (recent5['RSI'].shift(1) <= 30)).any())
    macd_signal = bool(
        ((recent5['MACD'] < 0) &
         (recent5['MACD'] > recent5['MACD_Signal']) &
         (recent5['MACD'].shift(1) <= recent5['MACD_Signal'].shift(1))).any()
    )

    div_window = df.tail(60)
    half = len(div_window) // 2
    older, newer = div_window.iloc[:half], div_window.iloc[half:]
    bullish_divergence = bool(
        (newer['SP500'].min() < older['SP500'].min()) and
        (newer['RSI'].min()   > older['RSI'].min())   and
        (newer['RSI'].min()   < 40)
    )

    stoch_rsi_bounce = bool(
        ((recent5['StochRSI_K'] > 20) & (recent5['StochRSI_K'].shift(1) <= 20)).any() and
        float(_safe(df['StochRSI_K'].iloc[-1], 50)) < 50
    )

    # BEAR 레짐에서 추세 신호 비활성화
    if regime == 'BEAR':
        ma_golden_cross = False
        macd_signal     = False

    # ── 3. 심리·신용 지표 (3_Sentiment) ───────────────────────────────
    hy_spread = float(_safe(latest.get('HY_Spread'), 3.0))

    roll = 252
    df['VIX_ZScore'] = (df['VIX'] - df['VIX'].rolling(roll).mean()) / df['VIX'].rolling(roll).std()
    df['HY_ZScore']  = (df['HY_Spread'] - df['HY_Spread'].rolling(roll).mean()) / df['HY_Spread'].rolling(roll).std()
    df['VIX_Pct']    = df['VIX'].rolling(roll).rank(pct=True) * 100
    df['HY_Pct']     = df['HY_Spread'].rolling(roll).rank(pct=True) * 100

    vix_z   = float(_safe(df['VIX_ZScore'].iloc[-1],  0))
    hy_z    = float(_safe(df['HY_ZScore'].iloc[-1],   0))
    vix_pct = float(_safe(df['VIX_Pct'].iloc[-1],    50))
    hy_pct  = float(_safe(df['HY_Pct'].iloc[-1],     50))

    vix_panic        = bool((recent5['VIX'] >= 30).any())
    vix_capitulation = bool(vix_panic and (latest['VIX'] < df.iloc[-2]['VIX']))
    credit_stress    = bool(hy_spread >= 5.0)
    extreme_fear     = bool(vix_z > 2.0)
    extreme_credit   = bool(hy_z  > 2.0)
    contrarian_buy   = bool(extreme_fear and not extreme_credit)

    # ── 4. 스마트머니 (4_Smart_Money) ─────────────────────────────────
    def ratio_signal(num_col, den_col, inverse=False):
        if num_col not in df.columns or den_col not in df.columns:
            return False
        ratio = df[num_col] / df[den_col].replace(0, float('nan'))
        ma50  = ratio.rolling(50).mean().iloc[-1]
        ma200 = ratio.rolling(200).mean().iloc[-1]
        if pd.isna(ma50) or pd.isna(ma200):
            return False
        return bool(ma50 < ma200) if inverse else bool(ma50 > ma200)

    spy_tlt_on = ratio_signal('SPY', 'TLT')
    xly_xlp_on = ratio_signal('XLY', 'XLP')
    xlk_xlu_on = ratio_signal('XLK', 'XLU')
    brk_spy_on = ratio_signal('BRK-B', 'SPY', inverse=True)

    smart_money_score = int(sum([spy_tlt_on, xly_xlp_on, xlk_xlu_on, brk_spy_on]))

    iwm_on = ratio_signal('IWM', 'SPY')
    qqq_on = ratio_signal('QQQ', 'SPY')
    gld_on = ratio_signal('GLD', 'SPY', inverse=True)  # 금 약세 = RISK ON

    # ── 5. 단기 스나이퍼 (5_Short_Term_Sniper) ────────────────────────
    df['SMA_20']   = df['SP500'].rolling(20).mean()
    df['STD_20']   = df['SP500'].rolling(20).std()
    df['BB_Lower'] = df['SMA_20'] - df['STD_20'] * 2
    df['BB_Upper'] = df['SMA_20'] + df['STD_20'] * 2
    df['SMA_5']    = df['SP500'].rolling(5).mean()
    df['Disp_5']   = (df['SP500'] / df['SMA_5'].replace(0, float('nan'))) * 100

    bb_buy    = bool(sp500 <= float(_safe(df['BB_Lower'].iloc[-1], sp500 - 1)))
    bb_sell   = bool(sp500 >= float(_safe(df['BB_Upper'].iloc[-1], sp500 + 1)))
    disp_5    = float(_safe(df['Disp_5'].iloc[-1], 100))
    disp_buy  = bool(disp_5 <= 99.0)
    disp_sell = bool(disp_5 >= 101.0)

    # ── 6. 거시경제 (6_Macro_Indicators) ──────────────────────────────
    fed_rate    = float(_safe(latest.get('Fed_Rate'),    2.0))
    unemployment = float(_safe(latest.get('Unemployment'), 4.0))
    oil_wti     = float(_safe(latest.get('Oil_WTI'),    70.0))

    if 'Fed_Rate' in df.columns and len(df) > 63:
        rate_3m = float(_safe(df['Fed_Rate'].iloc[-63], fed_rate))
        rate_rising = bool(fed_rate > rate_3m)
    else:
        rate_rising = False

    unemp_alert = bool(unemployment > 4.5)

    if 'Oil_WTI' in df.columns and len(df) > 63:
        oil_3m = float(_safe(df['Oil_WTI'].iloc[-63], oil_wti))
        oil_spike = bool(oil_3m > 0 and (oil_wti - oil_3m) / oil_3m > 0.30)
    else:
        oil_spike = False

    recession_score = int(sum([yield_inverted, rate_rising, unemp_alert, oil_spike]))

    # ── 7. 유동성 (1_Liquidity) ────────────────────────────────────────
    net_liq = float(_safe(latest.get('Net_Liquidity'), 0))
    if 'Net_Liquidity' in df.columns and len(df) > 21:
        net_liq_21d = float(_safe(df['Net_Liquidity'].iloc[-22], net_liq))
        net_liq_change = round(net_liq - net_liq_21d, 2)
    else:
        net_liq_change = 0.0

    # ── 8. 통합 점수 (main.py 로직) ────────────────────────────────────
    core_signals = [
        ma_golden_cross or rsi_signal,  # 타이밍 (둘 중 하나)
        vix_capitulation or contrarian_buy,  # 심리
        smart_money_score >= 3,  # 스마트머니
        bb_buy or disp_buy,  # 스나이퍼
    ]
    danger_flags = [credit_stress, recession_score >= 3, regime == 'BEAR']

    convergence_score = int(sum(core_signals))
    has_danger        = any(danger_flags)

    if has_danger and convergence_score == 0:
        allocation_pct = 0
    elif has_danger:
        allocation_pct = 25
    elif convergence_score == 4:
        allocation_pct = 100
    elif convergence_score == 3:
        allocation_pct = 75
    elif convergence_score == 2:
        allocation_pct = 50
    elif convergence_score == 1:
        allocation_pct = 25
    else:
        allocation_pct = 0

    bull_cnt = convergence_score
    bear_cnt = int(sum([credit_stress, recession_score >= 2]))
    signal_conflict = bool(bull_cnt >= 1 and bear_cnt >= 1)

    # ── 최종 딕셔너리 ──────────────────────────────────────────────────
    return {
        "date": date_str,
        "market_regime": {
            "regime":          regime,
            "sp500":           round(sp500, 2),
            "sma_50":          round(sma_50, 2),
            "sma_200":         round(sma_200, 2),
            "vix":             round(vix, 2),
            "yield_curve":     round(yield_curve, 3),
            "yield_inverted":  yield_inverted,
            "inversion_days":  inv_streak,
        },
        "trend": {
            "ma_golden_cross":    ma_golden_cross,
            "rsi":                round(rsi_val, 1),
            "rsi_signal":         rsi_signal,
            "macd_signal":        macd_signal,
            "bullish_divergence": bullish_divergence,
            "stoch_rsi_bounce":   stoch_rsi_bounce,
        },
        "sentiment": {
            "vix_value":       round(vix, 2),
            "vix_zscore":      round(vix_z, 2),
            "vix_percentile":  round(vix_pct, 1),
            "vix_panic":       vix_panic,
            "vix_capitulation":vix_capitulation,
            "hy_spread":       round(hy_spread, 3),
            "hy_zscore":       round(hy_z, 2),
            "hy_percentile":   round(hy_pct, 1),
            "credit_stress":   credit_stress,
            "extreme_fear":    extreme_fear,
            "extreme_credit":  extreme_credit,
            "contrarian_buy":  contrarian_buy,
        },
        "smart_money": {
            "spy_tlt_on":        spy_tlt_on,
            "xly_xlp_on":        xly_xlp_on,
            "xlk_xlu_on":        xlk_xlu_on,
            "brk_spy_on":        brk_spy_on,
            "score":             smart_money_score,
            "iwm_spy_on":        iwm_on,
            "qqq_spy_on":        qqq_on,
            "gld_spy_safe":      gld_on,
        },
        "sniper": {
            "bb_buy":      bb_buy,
            "bb_sell":     bb_sell,
            "disp_buy":    disp_buy,
            "disp_sell":   disp_sell,
            "disparity_5": round(disp_5, 2),
        },
        "macro": {
            "yield_inverted":   yield_inverted,
            "inversion_days":   inv_streak,
            "fed_rate":         round(fed_rate, 2),
            "rate_rising":      rate_rising,
            "unemployment":     round(unemployment, 1),
            "unemp_alert":      unemp_alert,
            "oil_wti":          round(oil_wti, 2),
            "oil_spike":        oil_spike,
            "recession_score":  recession_score,
        },
        "liquidity": {
            "net_liquidity":        round(net_liq, 0),
            "net_liquidity_21d_chg": round(net_liq_change, 0),
        },
        "convergence": {
            "score":           convergence_score,
            "allocation_pct":  allocation_pct,
            "signal_conflict": signal_conflict,
            "has_danger":      has_danger,
        },
    }
