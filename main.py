import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Command Center", page_icon="🛰️", layout="wide")


# =====================================================================
# 1. 신호 계산 함수
# =====================================================================

def get_timing_signal(df):
    sma_50  = df['SP500'].rolling(50).mean().iloc[-1]
    sma_200 = df['SP500'].rolling(200).mean().iloc[-1]
    latest  = df.iloc[-1]
    is_on   = (latest['SP500'] > sma_200) and (sma_50 > sma_200)
    return ("🟢 BUY", "추세 상승", is_on)


def get_sentiment_signal(df):
    latest   = df.iloc[-1]
    recent   = df.tail(5)
    if latest['HY_Spread'] >= 5.0:
        return ("🚨 DANGER", "신용 경색 발생", False)
    if (recent['VIX'] >= 30).any() and (latest['VIX'] < df.iloc[-2]['VIX']):
        return ("🟢 BUY", "시장 항복 (VIX 하락)", True)
    return ("⚪ NORMAL", "특이사항 없음", None)   # None = 중립


def get_smart_money_signal(df):
    spy_on = (df['SPY'] / df['TLT']).rolling(50).mean().iloc[-1] > \
             (df['SPY'] / df['TLT']).rolling(200).mean().iloc[-1]
    xly_on = (df['XLY'] / df['XLP']).rolling(50).mean().iloc[-1] > \
             (df['XLY'] / df['XLP']).rolling(200).mean().iloc[-1]
    xlk_on = (df['XLK'] / df['XLU']).rolling(50).mean().iloc[-1] > \
             (df['XLK'] / df['XLU']).rolling(200).mean().iloc[-1]
    brk_on = (df['BRK-B'] / df['SPY']).rolling(50).mean().iloc[-1] < \
             (df['BRK-B'] / df['SPY']).rolling(200).mean().iloc[-1]
    score  = sum([spy_on, xly_on, xlk_on, brk_on])
    is_on  = score >= 3
    if score >= 3:
        return (f"🟢 RISK ON",  f"공격 집중 ({score}/4)", True)
    elif score == 2:
        return (f"🟡 CAUTION",  f"방향성 탐색 ({score}/4)", None)
    else:
        return (f"🔴 RISK OFF", f"방어 태세 ({score}/4)", False)


def get_sniper_signal(df):
    latest   = df.iloc[-1]
    bb_lower = df['SP500'].rolling(20).mean().iloc[-1] - df['SP500'].rolling(20).std().iloc[-1] * 2
    disp_5   = (latest['SP500'] / df['SP500'].rolling(5).mean().iloc[-1]) * 100
    is_on    = latest['SP500'] <= bb_lower or disp_5 <= 99.0
    if is_on:
        return ("🔥 SNIPE", "단기 낙폭 과대", True)
    return ("⚪ WAIT", "타점 대기중", None)


# =====================================================================
# 2. 시장 레짐 감지
# =====================================================================

def get_market_regime(df):
    sma_50  = df['SP500'].rolling(50).mean().iloc[-1]
    sma_200 = df['SP500'].rolling(200).mean().iloc[-1]
    vix     = df['VIX'].iloc[-1] if 'VIX' in df.columns else 20

    # 수익률 곡선 역전 여부
    yield_inverted = False
    if 'Yield_Curve' in df.columns:
        yield_inverted = df['Yield_Curve'].iloc[-1] < 0

    if sma_50 > sma_200 and vix < 25:
        regime = "🟢 BULL"
        color  = "#00FF00"
        desc   = "추세 상승 + 변동성 안정"
    elif sma_50 < sma_200 or vix > 30:
        regime = "🔴 BEAR"
        color  = "#FF4B4B"
        desc   = "하락 추세 또는 급등 변동성"
    else:
        regime = "🟡 TRANSITION"
        color  = "#FFC107"
        desc   = "방향성 모색 중"

    inv_badge = " ⚠️ 수익률 곡선 역전" if yield_inverted else ""
    return regime, color, desc + inv_badge


# =====================================================================
# 3. 통합 점수 + 포지션 사이징
# =====================================================================

def get_convergence(signals):
    """True/False/None → 점수(0~4) 및 배포 권장 비중 계산"""
    score = sum(1 for _, _, v in signals if v is True)
    danger = any(v is False for _, _, v in signals)

    if danger and score == 0:
        alloc, msg = 0,  "📛 현금 100% — 위험 신호 우세"
    elif danger:
        alloc, msg = 25, "🛡️ 현금 75% — 혼재 신호, 최소 포지션"
    elif score == 4:
        alloc, msg = 100,"🚀 자본 100% 투입 — 역사적 최고 수준 정렬"
    elif score == 3:
        alloc, msg = 75, "🟢 자본 75% 투입 — 강한 매수 환경"
    elif score == 2:
        alloc, msg = 50, "🟡 자본 50% 투입 — 중립, 관망 유지"
    elif score == 1:
        alloc, msg = 25, "🟠 자본 25% — 소극적 포지션"
    else:
        alloc, msg = 0,  "⚪ 현금 보유 — 신호 없음"

    return score, alloc, msg


# =====================================================================
# 4. 신호 충돌 감지
# =====================================================================

def detect_conflict(signals):
    bull_count = sum(1 for _, _, v in signals if v is True)
    bear_count = sum(1 for _, _, v in signals if v is False)
    if bull_count >= 1 and bear_count >= 1:
        return True, f"⚠️ 신호 충돌: 매수 {bull_count}개 vs 위험 {bear_count}개 — 신규 진입 자제"
    return False, ""


# =====================================================================
# 5. UI
# =====================================================================

MODULE_REGISTRY = [
    {"title": "🎯 2. Market Timing",       "desc": "중장기 추세",        "calc": get_timing_signal},
    {"title": "🚨 3. Fear & Credit",       "desc": "시장 심리 및 신용",  "calc": get_sentiment_signal},
    {"title": "🦅 4. Smart Money",         "desc": "기관 자금 위험 선호도","calc": get_smart_money_signal},
    {"title": "🔫 5. Short-Term Sniper",   "desc": "단기 매수 타점",      "calc": get_sniper_signal},
]

st.title("🛰️ Main Command Center (종합 상황판)")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty or 'SP500' not in df.columns:
    st.info("👋 환영합니다! 데이터가 없습니다. 화면 맨 아래에서 초기 데이터를 수집해 주세요.")
else:
    st.caption(f"최종 업데이트 기준일: {df['Date'].iloc[-1].strftime('%Y-%m-%d')}")

    # ── 시장 레짐 배너 ─────────────────────────────────────────────
    regime, r_color, r_desc = get_market_regime(df)
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid #555;"
        f"border-radius:8px;padding:12px 20px;margin-bottom:18px;'>"
        f"<span style='font-size:1.1em;'>📡 <b>시장 레짐:</b> "
        f"<span style='color:{r_color};font-weight:bold;font-size:1.2em;'>{regime}</span>"
        f"&nbsp;&nbsp;<span style='color:#aaa;font-size:0.9em;'>{r_desc}</span></span>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── 신호 계산 ──────────────────────────────────────────────────
    results = []
    for module in MODULE_REGISTRY:
        try:
            out = module['calc'](df)
            results.append(out)          # (status_str, detail_str, bool_or_None)
        except Exception as e:
            results.append(("❓ ERROR", str(e), None))

    # ── 통합 점수 & 포지션 사이징 ──────────────────────────────────
    conv_score, alloc, alloc_msg = get_convergence(results)
    conflicted, conflict_msg     = detect_conflict(results)

    total = len([v for _, _, v in results if v is not None])
    gauge_html = ""
    bar_pct    = int(conv_score / 4 * 100)
    bar_color  = "#00FF00" if conv_score >= 3 else "#FFC107" if conv_score == 2 else "#FF4B4B"

    st.markdown(
        f"<div style='background:rgba(255,255,255,0.04);border:1px solid #555;"
        f"border-radius:10px;padding:16px 20px;margin-bottom:18px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<div><b style='font-size:1em;color:#ddd;'>🎯 신호 통합 점수</b>"
        f"<h1 style='margin:4px 0;color:{bar_color};'>{conv_score} / 4</h1>"
        f"<p style='margin:0;color:#aaa;font-size:0.9em;'>{alloc_msg}</p></div>"
        f"<div style='text-align:right;'>"
        f"<p style='margin:0 0 4px;color:#aaa;font-size:0.85em;'>권장 투자 비중</p>"
        f"<h2 style='margin:0;color:{bar_color};'>{alloc}%</h2></div></div>"
        f"<div style='background:#333;border-radius:4px;height:8px;margin-top:12px;'>"
        f"<div style='background:{bar_color};width:{bar_pct}%;height:8px;border-radius:4px;'></div></div>"
        f"</div>",
        unsafe_allow_html=True
    )

    if conflicted:
        st.warning(conflict_msg)

    st.divider()

    # ── 4개 신호 카드 ──────────────────────────────────────────────
    cols = st.columns(2)
    for i, (module, (status, detail, _)) in enumerate(zip(MODULE_REGISTRY, results)):
        col   = cols[i % 2]
        color = ("#00FF00" if "🟢" in status or "🔥" in status
                 else "#FF4B4B" if "🔴" in status or "🚨" in status
                 else "#FFC107" if "🟡" in status
                 else "#888888")
        with col:
            st.markdown(
                f"<div style='border:1px solid #444;border-radius:8px;padding:15px;"
                f"margin-bottom:15px;background-color:rgba(255,255,255,0.02);'>"
                f"<h5 style='margin-top:0;color:#ddd;'>{module['title']} "
                f"<span style='font-size:0.8em;color:#888;'>({module['desc']})</span></h5>"
                f"<h2 style='margin:10px 0;color:{color};'>{status}</h2>"
                f"<p style='margin-bottom:0;color:#aaa;font-size:0.9em;'>{detail}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── 상황판 해설 ────────────────────────────────────────────────
    with st.expander("📖 상황판 신호(State) 읽는 법 & 액션 가이드", expanded=False):
        st.markdown("""
        ### 시장 레짐 (Market Regime)
        | 레짐 | 조건 | 전략 |
        |------|------|------|
        | 🟢 BULL | 50MA > 200MA & VIX < 25 | 추세 추종 — 비중 확대 |
        | 🔴 BEAR | 50MA < 200MA or VIX > 30 | 방어 — 현금/채권 확대 |
        | 🟡 TRANSITION | 중간 상태 | 관망 — 신호 확인 후 진입 |

        > ⚠️ **수익률 곡선 역전** 표시가 있으면, 향후 6~12개월 내 경기침체 가능성이 높습니다. 레짐이 BULL이라도 경계 수위를 높이세요.

        ---

        ### 신호 통합 점수 & 권장 비중
        | 점수 | 권장 비중 | 해석 |
        |------|-----------|------|
        | 4/4 | 100% | 역사적으로 가장 강한 매수 환경 |
        | 3/4 | 75%  | 강한 상승 환경, 적극 매수 |
        | 2/4 | 50%  | 혼재, 현 포지션 유지 |
        | 1/4 | 25%  | 신호 약함, 소극적 진입 |
        | 0/4 | 0%   | 위험, 현금 보유 |

        > ⚠️ **신호 충돌**이 감지되면, 매수/위험 신호가 동시에 존재합니다. 신규 진입은 자제하고 신호 정렬을 기다리세요.

        ---

        ### 개별 신호
        * **⚪ WAIT** — 방향 불명확, 현금 보유가 최선
        * **🟢 BUY / RISK ON** — 기관 자금 유입, 심리 안정
        * **🟡 CAUTION** — 신호 혼재, 관망
        * **🔴 RISK OFF / DANGER** — 자금 이탈, 비중 축소
        * **🔥 SNIPE** — 단기 낙폭 과대, 반등 타점
        """)

# =====================================================================
# 6. 어드민 패널
# =====================================================================
st.markdown("<br><br><br><hr>", unsafe_allow_html=True)

with st.expander("⚙️ System Admin (DB Management)", expanded=False):
    st.caption("권한이 있는 관리자만 데이터를 업데이트할 수 있습니다.")
    pwd = st.text_input("Enter Passcode:", type="password", key="admin_pwd")

    MASTER_PASSWORD = "cap"

    if pwd == MASTER_PASSWORD:
        st.success("인증 완료. 시스템 접근이 허가되었습니다.")
        if st.button("🔄 최신 데이터 수집 (Get DB)", type="primary"):
            with st.spinner("위성 연결 중... 약 10~20초 소요됩니다."):
                try:
                    from utils.fetcher import update_database
                    success = update_database()
                    if success:
                        st.success("✅ DB 업데이트 완료! 화면을 새로고침하여 확인하세요.")
                        st.rerun()
                    else:
                        st.error("❌ 업데이트 실패: 데이터를 가져오지 못했습니다.")
                except ImportError as e:
                    st.error(f"❌ 경로 오류: utils/fetcher.py 파일을 찾을 수 없습니다. ({e})")
                except Exception as e:
                    st.error(f"❌ 치명적 오류 발생: {e}")
    elif pwd != "":
        st.error("접근 거부: 암호가 일치하지 않습니다.")
