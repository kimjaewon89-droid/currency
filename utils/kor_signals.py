"""
한국 외국인/기관 수급 신호 계산 모듈
kr_smart_money_db.csv → 수급 점수(0~4) + 위험 플래그
"""
import numpy as np
import pandas as pd


def compute_kor_supply_signals(df: pd.DataFrame) -> dict:
    """
    Parameters
    ----------
    df : kr_smart_money_db.csv 로드한 DataFrame
         필수 컬럼: Date, kospi_foreign_total, kospi_institutional_total

    Returns
    -------
    수급 신호 dict (JSON 직렬화 가능)
    """
    df = df.copy().sort_values("Date").reset_index(drop=True)
    ROLL = 252

    fi_col   = "kospi_foreign_total"
    inst_col = "kospi_institutional_total"

    # 컬럼 없으면 기본값 반환
    if fi_col not in df.columns or inst_col not in df.columns:
        return _default_signals()

    fi   = df[fi_col]
    inst = df[inst_col]

    # 억원 단위로 변환 (원 → 억원)
    fi_bn   = fi   / 1e8
    inst_bn = inst / 1e8

    # ── 5일/20일 누적 ──────────────────────────────────────────────────
    fi_5d   = fi_bn.rolling(5,  min_periods=1).sum()
    fi_20d  = fi_bn.rolling(20, min_periods=1).sum()
    inst_5d = inst_bn.rolling(5, min_periods=1).sum()

    # ── z-score (252일 기준) ───────────────────────────────────────────
    def zscore(s):
        mu  = s.rolling(ROLL, min_periods=60).mean()
        std = s.rolling(ROLL, min_periods=60).std().replace(0, np.nan)
        return (s - mu) / std

    fi_5d_z   = zscore(fi_5d)
    inst_5d_z = zscore(inst_5d)

    # ── 최신값 ────────────────────────────────────────────────────────
    fi_5d_val   = float(fi_5d.iloc[-1])
    fi_20d_val  = float(fi_20d.iloc[-1])
    inst_5d_val = float(inst_5d.iloc[-1])
    fi_1d_val   = float(fi_bn.iloc[-1])
    inst_1d_val = float(inst_bn.iloc[-1])
    fi_5d_z_val   = float(fi_5d_z.iloc[-1])   if not np.isnan(fi_5d_z.iloc[-1])   else 0.0
    inst_5d_z_val = float(inst_5d_z.iloc[-1]) if not np.isnan(inst_5d_z.iloc[-1]) else 0.0

    # ── 신호 4종 ──────────────────────────────────────────────────────
    # Signal 1: 외국인 단기 (5일 합산 z>0 AND 절대값 500억+)
    fi_flow_on = bool(fi_5d_z_val > 0 and fi_5d_val > 500)

    # Signal 2: 외국인 추세 (20일 합산이 5거래일 전보다 증가 + 양수)
    fi_trend_on = bool(
        len(fi_20d) > 6 and
        fi_20d_val > float(fi_20d.iloc[-6]) and
        fi_20d_val > 0
    )

    # Signal 3: 기관 단기 (5일 합산 z>0 AND 절대값 300억+)
    inst_flow_on = bool(inst_5d_z_val > 0 and inst_5d_val > 300)

    # Signal 4: 외국인+기관 동반 당일 순매수
    dual_buy_on = bool(fi_1d_val > 0 and inst_1d_val > 0)

    supply_score = int(sum([fi_flow_on, fi_trend_on, inst_flow_on, dual_buy_on]))

    # ── 위험 플래그 ───────────────────────────────────────────────────
    danger_fi_dump   = bool(fi_5d_val < -3000)           # 외국인 5일 3000억+ 순매도
    danger_dual_sell = bool(fi_1d_val < -500 and inst_1d_val < -300)  # 동반 대량 매도

    has_danger = danger_fi_dump or danger_dual_sell

    verdict = "BUY" if (supply_score >= 2 and not has_danger) else "WAIT"

    return {
        "supply_score":     supply_score,
        "fi_flow_on":       fi_flow_on,
        "fi_trend_on":      fi_trend_on,
        "inst_flow_on":     inst_flow_on,
        "dual_buy_on":      dual_buy_on,
        "fi_1d":            round(fi_1d_val, 0),
        "inst_1d":          round(inst_1d_val, 0),
        "fi_5d_sum":        round(fi_5d_val, 0),
        "fi_20d_sum":       round(fi_20d_val, 0),
        "inst_5d_sum":      round(inst_5d_val, 0),
        "fi_5d_zscore":     round(fi_5d_z_val, 2),
        "inst_5d_zscore":   round(inst_5d_z_val, 2),
        "danger_fi_dump":   danger_fi_dump,
        "danger_dual_sell": danger_dual_sell,
        "has_danger":       has_danger,
        "verdict":          verdict,
    }


def _default_signals() -> dict:
    return {
        "supply_score": 0, "fi_flow_on": False, "fi_trend_on": False,
        "inst_flow_on": False, "dual_buy_on": False,
        "fi_1d": 0, "inst_1d": 0, "fi_5d_sum": 0, "fi_20d_sum": 0,
        "inst_5d_sum": 0, "fi_5d_zscore": 0.0, "inst_5d_zscore": 0.0,
        "danger_fi_dump": False, "danger_dual_sell": False,
        "has_danger": False, "verdict": "WAIT",
    }
