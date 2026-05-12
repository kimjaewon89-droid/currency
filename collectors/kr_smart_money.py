"""
한국 주식시장 외국인/기관 수급(순매수) 데이터 수집기
=======================================================
라이브러리 : pykrx (pip install pykrx)
API 키     : 불필요 (KRX 공식 데이터 무료 제공)
수집 대상  : KOSPI/KOSDAQ 투자자별 순매수, KOSPI200 가격
갱신 주기  : 영업일 기준 일간 (T+1)

작성 기준  : pykrx 0.1.x / 0.2.x 양 버전 호환
"""

import time
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# pykrx 임포트 — 없을 경우 안내 메시지 출력
try:
    from pykrx import stock as krx
except ImportError:
    raise ImportError(
        "pykrx 라이브러리가 설치되지 않았습니다.\n"
        "설치 명령어: pip install pykrx"
    )

# ─────────────────────────────────────────────────────────────────────────────
# 1. 컬럼 매핑 정의
#    pykrx 원본 한글 컬럼명 → 우리가 사용할 영문 컬럼명
#    pykrx 버전별 컬럼명 차이를 candidates 리스트로 관리
# ─────────────────────────────────────────────────────────────────────────────

# 투자자별 거래 컬럼 매핑
# 구조: { 영문_컬럼명: [가능한_한글_컬럼명_후보, ...] }
TRADING_COL_MAP = {
    "foreign_total":     ["외국인합계", "외국인"],          # 외국인 순매수 합계
    "institutional_total": ["기관합계"],                   # 기관 순매수 합계
    "individual":        ["개인"],                         # 개인 순매수
    "other_corp":        ["기타법인"],                     # 기타법인 순매수
    "total_all":         ["전체"],                         # 전체 시장 순매수
    # 세부 기관 분류 (pykrx 버전에 따라 없을 수 있음)
    "fin_investment":    ["금융투자"],                     # 금융투자 (증권사)
    "insurance":         ["보험"],                         # 보험사
    "trust_fund":        ["투신"],                         # 투신(펀드)
    "bank":              ["은행"],                         # 은행
    "private_equity":    ["사모"],                         # 사모펀드
    "pension":           ["연기금등", "연기금"],            # 연기금
}

# KOSPI200 지수 OHLCV 컬럼 매핑
INDEX_COL_MAP = {
    "k200_open":   ["시가"],
    "k200_high":   ["고가"],
    "k200_low":    ["저가"],
    "k200_close":  ["종가"],
    "k200_volume": ["거래량"],
    "k200_value":  ["거래대금"],
}

# KRX 지수 코드
INDEX_CODES = {
    "KOSPI":   "1001",
    "KOSDAQ":  "2001",
    "KOSPI200": "1028",   # KOSPI200 지수
}

# pykrx 서버 과부하 방지용 요청 간 대기 시간 (초)
REQUEST_SLEEP = 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 2. 유틸리티 함수
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    pykrx 반환 DataFrame의 컬럼명을 영문으로 통일한다.

    Parameters
    ----------
    df      : pykrx가 반환한 원본 DataFrame (한글 컬럼)
    col_map : { 영문_컬럼명: [후보_한글_컬럼명, ...] } 딕셔너리

    Returns
    -------
    영문 컬럼명으로 변환된 DataFrame (매핑 안 된 컬럼은 제거)
    """
    rename_dict = {}
    for eng_name, candidates in col_map.items():
        for kr_name in candidates:
            if kr_name in df.columns:
                rename_dict[kr_name] = eng_name
                break  # 첫 번째 매칭에서 중단

    if not rename_dict:
        warnings.warn("컬럼 매핑 실패: pykrx 반환 컬럼명을 인식할 수 없습니다.")
        return pd.DataFrame()

    # 매핑된 컬럼만 선택하여 rename
    mapped_cols = list(rename_dict.keys())
    df_mapped = df[mapped_cols].rename(columns=rename_dict)
    return df_mapped


def _safe_fetch_trading(start: str, end: str, market: str) -> pd.DataFrame:
    """
    pykrx 투자자별 거래실적 API를 안전하게 호출한다.

    순매수 = 매수금액 - 매도금액 (pykrx가 이미 계산해서 반환)

    Parameters
    ----------
    start  : 조회 시작일 'YYYYMMDD'
    end    : 조회 종료일 'YYYYMMDD'
    market : 'KOSPI' 또는 'KOSDAQ'

    Returns
    -------
    영문 컬럼명이 적용된 DataFrame, 실패 시 빈 DataFrame
    """
    try:
        time.sleep(REQUEST_SLEEP)  # KRX 서버 과부하 방지
        df_raw = krx.get_market_trading_value_by_date(start, end, market)

        if df_raw is None or df_raw.empty:
            print(f"  [경고] {market} 투자자별 거래 데이터 없음 ({start}~{end})")
            return pd.DataFrame()

        # 컬럼명 영문 통일
        df_eng = _resolve_columns(df_raw, TRADING_COL_MAP)
        if df_eng.empty:
            print(f"  [경고] {market} 컬럼 매핑 실패. 실제 컬럼: {list(df_raw.columns)}")
            return pd.DataFrame()

        # 인덱스를 날짜 컬럼으로 전환
        df_eng.index.name = "Date"
        df_eng = df_eng.reset_index()
        df_eng["Date"] = pd.to_datetime(df_eng["Date"])

        # 숫자 타입 정규화 (단위: 원)
        num_cols = [c for c in df_eng.columns if c != "Date"]
        df_eng[num_cols] = df_eng[num_cols].apply(pd.to_numeric, errors="coerce")

        return df_eng

    except Exception as e:
        print(f"  [에러] {market} 투자자별 거래 수집 실패: {e}")
        return pd.DataFrame()


def _safe_fetch_index(start: str, end: str, index_code: str,
                      index_label: str) -> pd.DataFrame:
    """
    pykrx 지수 OHLCV API를 안전하게 호출한다.

    Parameters
    ----------
    start       : 조회 시작일 'YYYYMMDD'
    end         : 조회 종료일 'YYYYMMDD'
    index_code  : KRX 지수 코드 (예: '1028' = KOSPI200)
    index_label : 컬럼 prefix로 사용할 레이블 (예: 'k200')

    Returns
    -------
    영문 컬럼명이 적용된 DataFrame, 실패 시 빈 DataFrame
    """
    try:
        time.sleep(REQUEST_SLEEP)
        df_raw = krx.get_index_ohlcv_by_date(start, end, index_code)

        if df_raw is None or df_raw.empty:
            print(f"  [경고] 지수({index_code}) 데이터 없음 ({start}~{end})")
            return pd.DataFrame()

        df_eng = _resolve_columns(df_raw, INDEX_COL_MAP)
        if df_eng.empty:
            print(f"  [경고] 지수({index_code}) 컬럼 매핑 실패. 실제 컬럼: {list(df_raw.columns)}")
            return pd.DataFrame()

        df_eng.index.name = "Date"
        df_eng = df_eng.reset_index()
        df_eng["Date"] = pd.to_datetime(df_eng["Date"])

        num_cols = [c for c in df_eng.columns if c != "Date"]
        df_eng[num_cols] = df_eng[num_cols].apply(pd.to_numeric, errors="coerce")

        return df_eng

    except Exception as e:
        print(f"  [에러] 지수({index_code}) 수집 실패: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 3. 파생 지표 계산
# ─────────────────────────────────────────────────────────────────────────────

def _compute_derived_indicators(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """
    시장(prefix)별 파생 지표를 계산한다.

    Parameters
    ----------
    df     : 해당 시장의 투자자별 순매수 DataFrame (영문 컬럼)
    prefix : 'kospi' 또는 'kosdaq' — 컬럼명 앞에 붙을 접두어

    Returns
    -------
    파생 지표 컬럼이 추가된 DataFrame
    """
    df = df.copy().sort_values("Date").reset_index(drop=True)

    foreign_col = "foreign_total"
    inst_col    = "institutional_total"
    total_col   = "total_all"

    # ── 3-1. 5일 / 20일 누적 순매수 ──────────────────────────────────────
    # 외국인 누적 순매수
    if foreign_col in df.columns:
        df[f"{prefix}_foreign_net_5d"]  = df[foreign_col].rolling(5,  min_periods=1).sum()
        df[f"{prefix}_foreign_net_20d"] = df[foreign_col].rolling(20, min_periods=1).sum()

    # 기관 누적 순매수
    if inst_col in df.columns:
        df[f"{prefix}_inst_net_5d"]  = df[inst_col].rolling(5,  min_periods=1).sum()
        df[f"{prefix}_inst_net_20d"] = df[inst_col].rolling(20, min_periods=1).sum()

    # ── 3-2. 외국인 + 기관 동반 순매수 여부 (bool) ───────────────────────
    # 두 세력이 같은 날 동시에 순매수(양수)이면 True
    if foreign_col in df.columns and inst_col in df.columns:
        df[f"{prefix}_combined_buying"] = (
            (df[foreign_col] > 0) & (df[inst_col] > 0)
        )
        # 5일 연속 동반 순매수 일수 (추세 강도 보조 지표)
        df[f"{prefix}_combined_buying_streak"] = (
            df[f"{prefix}_combined_buying"]
            .astype(int)
            .groupby((~df[f"{prefix}_combined_buying"]).cumsum())
            .cumsum()
        )

    # ── 3-3. 순매수 강도 (순매수 / 전체 거래대금) ────────────────────────
    # 절대금액이 아닌 거래 대비 비율로 정규화 → 시장 규모 변화 영향 제거
    if total_col in df.columns:
        # 거래대금 대신 total_all의 절댓값 합산을 분모로 사용
        # (pykrx get_market_trading_value_by_date는 순매수 기준)
        # 거래대금은 별도로 get_market_trading_value_by_date(detail=True)를 써야 하므로
        # 여기서는 외국인/기관/개인 절댓값의 합을 대용 거래대금으로 사용
        pass

    # 거래대금 대용치: 모든 투자자 순매수 절댓값 합산
    value_cols = [c for c in df.columns
                  if c in ["foreign_total", "institutional_total", "individual",
                            "other_corp", "fin_investment", "insurance",
                            "trust_fund", "bank"]]
    if value_cols:
        proxy_volume = df[value_cols].abs().sum(axis=1).replace(0, np.nan)

        if foreign_col in df.columns:
            df[f"{prefix}_foreign_intensity"] = (
                df[foreign_col] / proxy_volume
            ).clip(-1, 1)  # -100% ~ +100% 범위로 제한

        if inst_col in df.columns:
            df[f"{prefix}_inst_intensity"] = (
                df[inst_col] / proxy_volume
            ).clip(-1, 1)

    # ── 3-4. 컬럼명에 prefix 붙이기 (원본 기본 컬럼 포함) ─────────────────
    # 원본 컬럼 (Date 제외)에도 시장 prefix 추가
    basic_cols = list(TRADING_COL_MAP.keys())  # 영문 기본 컬럼명 목록
    rename_map = {}
    for col in df.columns:
        if col == "Date":
            continue
        if col in basic_cols:
            # 기본 수급 컬럼: kospi_foreign_total 등
            rename_map[col] = f"{prefix}_{col}"
        # 이미 prefix가 붙은 파생 컬럼은 그대로 유지

    df = df.rename(columns=rename_map)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. 메인 수집 함수
# ─────────────────────────────────────────────────────────────────────────────

def fetch_kr_smart_money(
    years: int = 2,
    include_detail: bool = True,
) -> pd.DataFrame:
    """
    한국 주식시장 외국인/기관 수급 데이터를 수집하고 파생 지표를 계산한다.

    Parameters
    ----------
    years          : 수집 기간 (년). 기본값 2년
    include_detail : 세부 기관(금융투자/보험/투신/은행) 포함 여부

    Returns
    -------
    pandas DataFrame — 날짜 기준 정렬, 컬럼명 영문
    실패 시 빈 DataFrame 반환

    컬럼 구조
    ----------
    Date                       : 날짜
    kospi_foreign_total        : KOSPI 외국인합계 순매수 (원)
    kospi_institutional_total  : KOSPI 기관합계 순매수 (원)
    kospi_individual           : KOSPI 개인 순매수 (원)
    kospi_fin_investment       : KOSPI 금융투자 순매수 (원)
    kospi_insurance            : KOSPI 보험 순매수 (원)
    kospi_trust_fund           : KOSPI 투신 순매수 (원)
    kospi_bank                 : KOSPI 은행 순매수 (원)
    kospi_pension              : KOSPI 연기금 순매수 (원)
    kospi_foreign_net_5d       : KOSPI 외국인 5일 누적 순매수
    kospi_foreign_net_20d      : KOSPI 외국인 20일 누적 순매수
    kospi_inst_net_5d          : KOSPI 기관 5일 누적 순매수
    kospi_inst_net_20d         : KOSPI 기관 20일 누적 순매수
    kospi_combined_buying      : KOSPI 외국인+기관 동반 순매수 (bool)
    kospi_foreign_intensity    : KOSPI 외국인 순매수 강도 (-1~1)
    kospi_inst_intensity       : KOSPI 기관 순매수 강도 (-1~1)
    kosdaq_*                   : KOSDAQ 동일 구조
    k200_open/high/low/close   : KOSPI200 지수 OHLCV
    k200_volume                : KOSPI200 거래량
    """
    print("=" * 60)
    print("한국 주식시장 수급 데이터 수집 시작")
    print("=" * 60)

    # ── 날짜 범위 설정 ────────────────────────────────────────────────────
    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=365 * years + 10)  # 여유분 10일 추가
    start_str = start_dt.strftime("%Y%m%d")
    end_str   = end_dt.strftime("%Y%m%d")
    print(f"  수집 기간: {start_str} ~ {end_str}")

    # ── KOSPI 투자자별 거래 수집 ──────────────────────────────────────────
    print("\n[1/3] KOSPI 투자자별 순매수 수집 중...")
    df_kospi_raw = _safe_fetch_trading(start_str, end_str, "KOSPI")

    if df_kospi_raw.empty:
        print("  [실패] KOSPI 데이터 수집 불가. 빈 DataFrame 반환.")
        return pd.DataFrame()

    df_kospi = _compute_derived_indicators(df_kospi_raw, "kospi")
    print(f"  완료: {len(df_kospi)}행, {len(df_kospi.columns)}컬럼")

    # ── KOSDAQ 투자자별 거래 수집 ─────────────────────────────────────────
    print("\n[2/3] KOSDAQ 투자자별 순매수 수집 중...")
    df_kosdaq_raw = _safe_fetch_trading(start_str, end_str, "KOSDAQ")

    if df_kosdaq_raw.empty:
        print("  [경고] KOSDAQ 데이터 수집 실패. KOSPI만으로 진행.")
        df_kosdaq = pd.DataFrame(columns=["Date"])
    else:
        df_kosdaq = _compute_derived_indicators(df_kosdaq_raw, "kosdaq")
        print(f"  완료: {len(df_kosdaq)}행, {len(df_kosdaq.columns)}컬럼")

    # ── KOSPI200 지수 가격 데이터 수집 ────────────────────────────────────
    print("\n[3/3] KOSPI200 지수 데이터 수집 중...")
    df_k200 = _safe_fetch_index(start_str, end_str, INDEX_CODES["KOSPI200"], "k200")

    if df_k200.empty:
        print("  [경고] KOSPI200 데이터 수집 실패.")
    else:
        print(f"  완료: {len(df_k200)}행")

    # ── 데이터 병합 ───────────────────────────────────────────────────────
    print("\n[병합] 세 데이터셋 날짜 기준 병합 중...")

    # KOSPI를 기준으로 outer join (날짜 기준 정렬)
    df_merged = df_kospi.copy()

    if not df_kosdaq.empty and "Date" in df_kosdaq.columns:
        df_merged = pd.merge(df_merged, df_kosdaq, on="Date", how="outer")

    if not df_k200.empty and "Date" in df_k200.columns:
        df_merged = pd.merge(df_merged, df_k200, on="Date", how="outer")

    # 날짜 정렬 및 중복 제거
    df_merged = (
        df_merged
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    # ── 결측치 처리 ───────────────────────────────────────────────────────
    # 휴장일(날짜 gap)은 forward fill (직전 거래일 값 유지)
    num_cols = [c for c in df_merged.columns if c != "Date"]
    df_merged[num_cols] = df_merged[num_cols].ffill()

    # ── 데이터 품질 검증 ──────────────────────────────────────────────────
    _validate_data_quality(df_merged)

    print(f"\n수집 완료: 총 {len(df_merged)}행, {len(df_merged.columns)}개 컬럼")
    print(f"날짜 범위: {df_merged['Date'].min().date()} ~ {df_merged['Date'].max().date()}")
    print("=" * 60)

    return df_merged


# ─────────────────────────────────────────────────────────────────────────────
# 5. 데이터 품질 검증
# ─────────────────────────────────────────────────────────────────────────────

def _validate_data_quality(df: pd.DataFrame) -> None:
    """
    수집된 DataFrame의 기본 품질을 검증하고 경고를 출력한다.
    """
    print("\n[데이터 품질 검증]")

    # DQ-001: NaN 비율 체크
    nan_ratio = df.isnull().mean()
    high_nan = nan_ratio[nan_ratio > 0.05]
    if not high_nan.empty:
        print(f"  [경고] NaN 비율 5% 초과 컬럼: {list(high_nan.index)}")
    else:
        print("  [OK] NaN 비율 정상 (모든 컬럼 < 5%)")

    # DQ-002: 날짜 단조증가 확인
    if df["Date"].is_monotonic_increasing:
        print("  [OK] 날짜 인덱스 단조증가 확인")
    else:
        print("  [경고] 날짜 순서 이상 감지")

    # DQ-005: 수집 행 수 확인 (2년 영업일 약 498일)
    expected_rows = 498
    actual_rows   = len(df)
    if actual_rows < expected_rows * 0.9:
        print(f"  [경고] 예상 행 수({expected_rows})보다 적음: {actual_rows}행")
    else:
        print(f"  [OK] 행 수 정상: {actual_rows}행")

    # 핵심 컬럼 존재 여부 확인
    required = ["kospi_foreign_total", "kospi_institutional_total",
                "kospi_combined_buying"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        print(f"  [경고] 필수 컬럼 누락: {missing}")
    else:
        print("  [OK] 필수 컬럼 모두 존재")


# ─────────────────────────────────────────────────────────────────────────────
# 6. 저장 / 업데이트 함수 (utils/fetcher.py 패턴과 동일)
# ─────────────────────────────────────────────────────────────────────────────

def update_kr_smart_money_db(
    save_path: str = "kr_smart_money_db.csv",
    years: int = 2,
) -> bool:
    """
    한국 수급 데이터를 수집하고 CSV로 저장한다.
    utils/fetcher.py의 update_database() 패턴을 따른다.

    Parameters
    ----------
    save_path : 저장 경로 (기본: 프로젝트 루트 kr_smart_money_db.csv)
    years     : 수집 기간 (년)

    Returns
    -------
    성공 여부 (bool)
    """
    try:
        df = fetch_kr_smart_money(years=years)

        if df.empty:
            print("❌ 수급 데이터 수집 실패: 빈 DataFrame")
            return False

        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"✅ 한국 수급 DB 저장 완료! → {save_path}")
        print(f"   마지막 날짜: {df['Date'].max().strftime('%Y-%m-%d')}")
        return True

    except Exception as e:
        print(f"❌ 치명적 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 7. 편의 함수 — 기존 DB와 병합
# ─────────────────────────────────────────────────────────────────────────────

def merge_with_liquidity_db(
    kr_df: pd.DataFrame,
    liquidity_csv_path: str = "liquidity_db.csv",
) -> pd.DataFrame:
    """
    fetch_kr_smart_money()의 결과를 기존 liquidity_db.csv와 날짜 기준으로 병합한다.
    SP500과 KOSPI200을 같은 화면에서 비교할 수 있도록 한다.

    Parameters
    ----------
    kr_df             : fetch_kr_smart_money() 반환 DataFrame
    liquidity_csv_path : 기존 liquidity_db.csv 경로

    Returns
    -------
    병합된 DataFrame (Date 기준 정렬, 결측치 ffill 처리)
    """
    import os

    if not os.path.exists(liquidity_csv_path):
        print(f"  [경고] {liquidity_csv_path} 없음 — 한국 수급 데이터만 반환")
        return kr_df

    liq_df = pd.read_csv(liquidity_csv_path)
    liq_df["Date"] = pd.to_datetime(liq_df["Date"])

    if kr_df.empty:
        return liq_df

    # outer join으로 날짜 범위 최대 포함
    merged = pd.merge(liq_df, kr_df, on="Date", how="outer")
    merged = (
        merged
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    # 각 컬럼 ffill (미래 방향 역채움 방지)
    num_cols = [c for c in merged.columns if c != "Date"]
    merged[num_cols] = merged[num_cols].ffill()

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# 8. 단독 실행 테스트
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 직접 실행 시 수집 → 저장 → 미리보기
    success = update_kr_smart_money_db(
        save_path="kr_smart_money_db.csv",
        years=2,
    )

    if success:
        df_result = pd.read_csv("kr_smart_money_db.csv")
        df_result["Date"] = pd.to_datetime(df_result["Date"])
        print("\n[미리보기 — 최근 5일]")
        print(df_result.tail(5).to_string())
        print(f"\n전체 컬럼 ({len(df_result.columns)}개):")
        for col in df_result.columns:
            print(f"  {col}")
