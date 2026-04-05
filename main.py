import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Command Center", page_icon="🛰️", layout="wide")


# =====================================================================
# 🛠️ 1. 전술 모듈 등록소 (Plugin Registry)
# 새로운 페이지를 만들면, UI를 고칠 필요 없이 이곳에 계산 로직만 추가하세요.
# =====================================================================

def get_timing_signal(df):
    latest = df.iloc[-1]
    sma_50 = df['SP500'].rolling(50).mean().iloc[-1]
    sma_200 = df['SP500'].rolling(200).mean().iloc[-1]
    is_on = (latest['SP500'] > sma_200) and (sma_50 > sma_200)
    return ("🟢 BUY", "추세 상승") if is_on else ("⚪ WAIT", "관망 (역배열)")


def get_sentiment_signal(df):
    latest = df.iloc[-1]
    if latest['HY_Spread'] >= 5.0: return ("🚨 DANGER", "신용 경색 발생")
    if (df['VIX'].tail(5) >= 30).any() and (latest['VIX'] < df.iloc[-2]['VIX']): return ("🟢 BUY", "시장 항복 (VIX 하락)")
    return ("⚪ NORMAL", "특이사항 없음")


def get_smart_money_signal(df):
    # 각 비율의 50MA > 200MA 여부 판별
    spy_on = (df['SPY'] / df['TLT']).rolling(50).mean().iloc[-1] > (df['SPY'] / df['TLT']).rolling(200).mean().iloc[-1]
    xly_on = (df['XLY'] / df['XLP']).rolling(50).mean().iloc[-1] > (df['XLY'] / df['XLP']).rolling(200).mean().iloc[-1]
    xlk_on = (df['XLK'] / df['XLU']).rolling(50).mean().iloc[-1] > (df['XLK'] / df['XLU']).rolling(200).mean().iloc[-1]
    brk_on = (df['BRK-B'] / df['SPY']).rolling(50).mean().iloc[-1] < (df['BRK-B'] / df['SPY']).rolling(200).mean().iloc[
        -1]
    score = sum([spy_on, xly_on, xlk_on, brk_on])

    if score >= 3:
        return (f"🟢 RISK ON", f"공격 집중 ({score}/4)")
    elif score == 2:
        return (f"🟡 CAUTION", f"방향성 탐색 ({score}/4)")
    else:
        return (f"🔴 RISK OFF", f"방어 태세 ({score}/4)")


def get_sniper_signal(df):
    latest = df.iloc[-1]
    bb_lower = df['SP500'].rolling(20).mean().iloc[-1] - (df['SP500'].rolling(20).std().iloc[-1] * 2)
    disp_5 = (latest['SP500'] / df['SP500'].rolling(5).mean().iloc[-1]) * 100
    if latest['SP500'] <= bb_lower or disp_5 <= 99.0: return ("🔥 SNIPE", "단기 낙폭 과대")
    return ("⚪ WAIT", "타점 대기중")


# 📌 여기에 모듈을 등록하기만 하면 화면은 자동으로 생성됩니다.
MODULE_REGISTRY = [
    {"title": "🎯 2. Market Timing", "desc": "중장기 추세", "calc": get_timing_signal},
    {"title": "🚨 3. Fear & Credit", "desc": "시장 심리 및 신용", "calc": get_sentiment_signal},
    {"title": "🦅 4. Smart Money", "desc": "기관 자금 위험 선호도", "calc": get_smart_money_signal},
    {"title": "🔫 5. Short-Term Sniper", "desc": "단기 매수 타점", "calc": get_sniper_signal},
]

# =====================================================================
# 🖥️ 2. UI 자동 렌더링 엔진 (건드릴 필요 없음)
# =====================================================================

st.title("🛰️ Main Command Center (종합 상황판)")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'): return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty or 'SP500' not in df.columns:
    st.info("👋 환영합니다! 데이터가 없습니다. 화면 맨 아래에서 초기 데이터를 수집해 주세요.")
else:
    st.caption(f"최종 업데이트 기준일: {df['Date'].iloc[-1].strftime('%Y-%m-%d')}")

    # 2열 그리드로 자동 배치
    cols = st.columns(2)
    for i, module in enumerate(MODULE_REGISTRY):
        col = cols[i % 2]  # 짝수/홀수 인덱스에 따라 왼쪽/오른쪽 배치
        try:
            status, detail = module['calc'](df)
            color = "#00FF00" if "🟢" in status or "🔥" in status else "#FF4B4B" if "🔴" in status or "🚨" in status else "#FFC107" if "🟡" in status else "#888888"

            with col:
                st.markdown(f"""
                <div style="border:1px solid #444; border-radius:8px; padding:15px; margin-bottom:15px; background-color: rgba(255,255,255,0.02);">
                    <h5 style="margin-top:0; color:#ddd;">{module['title']} <span style='font-size:0.8em; color:#888;'>({module['desc']})</span></h5>
                    <h2 style="margin:10px 0; color:{color};">{status}</h2>
                    <p style="margin-bottom:0; color:#aaa; font-size:0.9em;">{detail}</p>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            col.error(f"{module['title']} 계산 오류: {e}")

# 4. 상황판 상태(State) 정밀 해설
with st.expander("📖 상황판 신호(State) 읽는 법 & 액션 가이드", expanded=False):
    st.markdown("""
    상황판에 표시되는 각 단어는 현재 시장의 **'온도'**와 우리가 취해야 할 **'전술적 행동'**을 의미합니다.

    ---

    ### ⚪ WAIT (관망 / 대기)
    * **의미:** 시장이 뚜렷한 방향을 잡지 못했거나, 에너지를 응축 중인 상태입니다.
    * **액션:** 서둘러 방아쇠를 당기지 마세요. 현금을 보유하며 다음 기회를 기다리는 것이 가장 훌륭한 전략입니다. "안 하는 것도 투자"라는 격언이 적용되는 시기입니다.

    ---

    ### 🟢 BUY / RISK ON (매수 / 공격 개시)
    * **의미:** 시장의 모든 지표가 '상승'을 가리키고 있습니다. 기관들의 자금이 주식 시장으로 유입되고 있으며, 심리적으로도 안정된 상태입니다.
    * **액션:** 자신 있게 비중을 늘려도 좋은 시기입니다. 주도주(기술주 등)를 중심으로 포트폴리오를 구성하여 수익을 극대화하세요.

    ---

    ### 🟡 CAUTION (주의 / 경계)
    * **의미:** 상승세가 둔화되거나, 지표들 사이에 충돌이 발생한 상태입니다. (예: 가격은 오르는데 자금은 빠져나가는 중)
    * **액션:** 신규 매수는 자제하고, 이미 수익이 난 종목은 일부 현금화하여 수익을 챙겨두세요. 폭풍 전야의 고요함일 수 있으니 안전벨트를 매야 합니다.

    ---

    ### 🔴 RISK OFF / DANGER (위험 / 후퇴)
    * **의미:** 시장의 자금이 안전 자산(금, 채권)으로 빠르게 도망치고 있습니다. 경제 위기 징후나 심각한 신용 경색이 감지된 상태입니다.
    * **액션:** **비상탈출!** 주식 비중을 최소화하고 현금을 확보하여 함선을 방어하세요. 이때 무리하게 '물타기'를 하는 것은 침몰하는 배에 짐을 더 싣는 것과 같습니다.

    ---

    ### 🔥 SNIPE (단기 저격 타점)
    * **의미:** 대세 흐름과 상관없이, 단기적으로 주가가 너무 과하게 떨어져서 **'용수철처럼 튀어 오를 준비'**가 된 상태입니다.
    * **액션:** 발 빠른 단기 수익을 노리는 저격수에게 최고의 기회입니다. 짧게 먹고 나오는 전술적 매수가 유효합니다.
    """)

# =====================================================================
# 🔐 3. 데이터베이스 수집 관리 (보안 구역)
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
                    # ✅ Captain의 디렉토리 구조에 맞춰 utils 폴더에서 import
                    import sys
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