import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Smart Money Flow", layout="wide")

# 1. 데이터 로드 및 검증
# 1. 데이터 로드 및 검증 (수정된 버전)
@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 💡 추가된 안전장치: 빈칸을 이전 값으로 채우고, 
    # 데이터가 부족하면 0으로라도 채워서 에러를 방지합니다.
    df = df.sort_values('Date').ffill().fillna(0)
    return df.reset_index(drop=True)

df = load_data()

# 필수 종목이 DB에 있는지 확인
required_tickers = ['SPY', 'TLT', 'XLY', 'XLP', 'XLK', 'XLU', 'BRK-B']
missing = [t for t in required_tickers if t not in df.columns]

if missing:
    st.error(f"⚠️ 다음 데이터가 누락되었습니다: {', '.join(missing)}\n\nfetcher.py에 종목을 추가하고 [Get DB]를 다시 실행해주세요.")
    st.stop()


st.title("🦅 Smart Money Flow (워런 버핏의 렌즈)")

# 2. 비율(Ratio) 및 이동평균선 계산
# (비율이 50일선 > 200일선이면 '상승 추세'로 판단합니다)
ratios = {
    'SPY_TLT': ('SPY', 'TLT'),       # 주식 vs 채권
    'XLY_XLP': ('XLY', 'XLP'),       # 사치재 vs 필수재
    'XLK_XLU': ('XLK', 'XLU'),       # 기술주 vs 유틸리티
    'BRK_SPY': ('BRK-B', 'SPY')      # 가치주 vs 시장평균
}

for name, (num, den) in ratios.items():
    df[name] = df[num] / df[den]
    df[f'{name}_50MA'] = df[name].rolling(window=50).mean()
    df[f'{name}_200MA'] = df[name].rolling(window=200).mean()

latest = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# 3. 시그널 판별 (ON = 시장이 건강하고 공격(매수)할 때)
# 주식, 사치재, 기술주 비율은 오르는 게 좋음 (50MA > 200MA)
risk_on_spy = latest['SPY_TLT_50MA'] > latest['SPY_TLT_200MA']
risk_on_xly = latest['XLY_XLP_50MA'] > latest['XLY_XLP_200MA']
risk_on_xlk = latest['XLK_XLU_50MA'] > latest['XLK_XLU_200MA']

# 버크셔(가치/방어) 비율은 '내려가는' 게 대세 상승장임 (50MA < 200MA 이면 주식시장 ON)
risk_on_brk = latest['BRK_SPY_50MA'] < latest['BRK_SPY_200MA']

# 종합 매수 판별
score = sum([risk_on_spy, risk_on_xly, risk_on_xlk, risk_on_brk])

st.subheader(f"📊 최종 매수/매도 판독기 (기준일: {latest_date})")

# 종합 스코어에 따른 행동 지침
if score == 4:
    st.success("🚀 **[FULL ATTACK] 완벽한 대세 상승장입니다.** 스마트 머니가 주식/기술주/소비재로 맹렬하게 쏟아지고 있습니다. 적극 매수하세요.")
elif score == 3:
    st.info("🟢 **[BUY] 좋은 매수 환경입니다.** 시장의 체력이 튼튼합니다. 비중을 늘려도 좋습니다.")
elif score == 2:
    st.warning("🟡 **[HOLD / CAUTION] 시장이 방향을 고민 중입니다.** 공격과 방어가 팽팽합니다. 관망하거나 방어주 비율을 높이세요.")
else:
    st.error("🚨 **[DEFENSE] 하락장 경보 발령!** 스마트 머니가 채권과 방어주로 대피했습니다. 주식을 팔고 현금/채권을 확보하세요.")

st.divider()

col1, col2, col3, col4 = st.columns(4)

def get_status(is_on):
    return "<h3 style='text-align: center; color: #00FF00;'>RISK ON 🟢</h3>" if is_on else "<h3 style='text-align: center; color: #FF4B4B;'>RISK OFF 🔴</h3>"

with col1:
    st.markdown("<p style='text-align: center;'><b>시장 중력 (SPY/TLT)</b><br>주식 vs 장기국채</p>", unsafe_allow_html=True)
    st.markdown(get_status(risk_on_spy), unsafe_allow_html=True)
with col2:
    st.markdown("<p style='text-align: center;'><b>소비 체력 (XLY/XLP)</b><br>사치재 vs 필수재</p>", unsafe_allow_html=True)
    st.markdown(get_status(risk_on_xly), unsafe_allow_html=True)
with col3:
    st.markdown("<p style='text-align: center;'><b>공격 본능 (XLK/XLU)</b><br>기술주 vs 유틸리티</p>", unsafe_allow_html=True)
    st.markdown(get_status(risk_on_xlk), unsafe_allow_html=True)
with col4:
    st.markdown("<p style='text-align: center;'><b>가치 대피소 (BRK.B/SPY)</b><br>버크셔 vs 시장평균</p>", unsafe_allow_html=True)
    st.markdown(get_status(risk_on_brk), unsafe_allow_html=True)


st.divider()

# 5. 차트 시각화
fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    subplot_titles=("SPY / TLT (Stocks vs Bonds)", "XLY / XLP (Discretionary vs Staples)",
                                    "XLK / XLU (Tech vs Utilities)", "BRK-B / SPY (Berkshire vs Market)"))

plot_df = df.tail(252 * 2) # 최근 2년 데이터

colors = ['cyan', 'orange', 'violet', 'lightgreen']
keys = ['SPY_TLT', 'XLY_XLP', 'XLK_XLU', 'BRK_SPY']

for i, key in enumerate(keys):
    row = i + 1
    # 비율 자체
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[key], name="Ratio", line=dict(color=colors[i], width=1.5)), row=row, col=1)
    # 50일선 (단기 추세)
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_50MA'], name="50MA", line=dict(color='white', width=1.5)), row=row, col=1)
    # 200일선 (장기 추세)
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_200MA'], name="200MA", line=dict(color='gray', width=1.5, dash='dot')), row=row, col=1)

fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified", showlegend=False)

# 타이틀 폰트 크기 조정
for i in fig['layout']['annotations']:
    i['font'] = dict(size=14, color='white')

st.plotly_chart(fig, use_container_width=True)

# 4. AI 해설 영역 (초보자 맞춤형)
with st.expander("🤖 AI 트레이딩 어시스턴트: 이 4가지 불빛이 의미하는 것 (초보자 가이드)", expanded=True):
    st.markdown("""
    이 화면은 기관 투자자(스마트 머니)들이 **'어느 바구니에 돈을 담고 있는가?'**를 추적하여, 지금 주식을 사도 되는지(RISK ON) 팔아야 하는지(RISK OFF)를 알려줍니다. 단기 50일선이 장기 200일선 위에 있으면 해당 비율이 '상승 추세'임을 뜻합니다.

    * **1. 시장 중력 (주식 SPY vs 채권 TLT)**
        * 🟢 **RISK ON:** 큰돈이 '안전한 이자(채권)'를 포기하고 '위험한 수익(주식)'을 선택했다는 뜻입니다. 대세 상승장의 기본 조건입니다.
    * **2. 소비 체력 (사치재 XLY vs 필수재 XLP)**
        * **"소고기(외식) vs 라면(생필품)"의 대결입니다.**
        * 🟢 **RISK ON:** 사람들이 라면 대신 소고기를 사 먹기 시작했습니다. 실물 경제가 정말로 건강하고 사람들이 돈을 쓰고 있다는 강력한 증거입니다.
    * **3. 공격 본능 (기술주 XLK vs 유틸리티 XLU)**
        * **"공격수(AI/반도체) vs 골키퍼(전기/가스)"의 대결입니다.**
        * 🟢 **RISK ON:** 시장이 미래 성장에 열광하며 공격수를 투입 중입니다. 나스닥이나 기술주 위주로 투자하기 아주 좋은 시점입니다.
    * **4. 가치 대피소 (버크셔 BRK.B vs S&P500 SPY)**
        * 워런 버핏의 회사는 현금이 많고 튼튼해서 시장이 폭락할 때 빛을 발합니다. (즉, 이 비율은 **반대로 움직여야** 주식시장에 좋습니다.)
        * 🟢 **RISK ON:** 버크셔보다 일반 시장(SPY)이 더 잘 나갑니다. 즉, 시장에 거품이나 위기감이 없고 투자자들이 마음 놓고 달리고 있다는 뜻입니다.
        * 🔴 만약 이 불빛이 꺼지면(버크셔가 시장을 이기기 시작하면), 스마트 머니가 "이제 튼튼한 벙커로 숨자"며 대피를 시작했다는 무서운 경고등입니다.
    """)
