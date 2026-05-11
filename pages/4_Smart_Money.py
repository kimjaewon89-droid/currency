import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Smart Money Flow", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    # 가격 컬럼은 ffill만 — fillna(0) 사용 금지 (비율 계산 왜곡 방지)
    price_cols = ['SPY', 'TLT', 'XLY', 'XLP', 'XLK', 'XLU', 'BRK-B', 'GLD', 'IWM', 'QQQ', 'SP500']
    existing = [c for c in price_cols if c in df.columns]
    df[existing] = df[existing].ffill()
    return df


df = load_data()

required_tickers = ['SPY', 'TLT', 'XLY', 'XLP', 'XLK', 'XLU', 'BRK-B']
missing = [t for t in required_tickers if t not in df.columns]

if df.empty or missing:
    st.error(f"⚠️ 데이터가 없거나 필수 지표({', '.join(missing) if missing else ''})가 누락되었습니다. 메인 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("🦅 Smart Money Flow (워런 버핏의 렌즈)")

# ── 비율 계산 ──────────────────────────────────────────────────────────
# 기본 4종 비율 (필수)
base_ratios = {
    'SPY_TLT': ('SPY', 'TLT'),    # 주식 vs 채권
    'XLY_XLP': ('XLY', 'XLP'),    # 사치재 vs 필수재
    'XLK_XLU': ('XLK', 'XLU'),    # 기술주 vs 유틸리티
    'BRK_SPY':  ('BRK-B', 'SPY'), # 가치주 vs 시장 (역방향)
}

# 확장 비율 (새 티커가 있을 때만 추가)
ext_ratios = {}
if 'IWM' in df.columns and 'SPY' in df.columns:
    ext_ratios['IWM_SPY'] = ('IWM', 'SPY')   # 소형주 vs 대형주 (리스크 선호)
if 'QQQ' in df.columns and 'SPY' in df.columns:
    ext_ratios['QQQ_SPY'] = ('QQQ', 'SPY')   # 성장주 vs 시장 (모멘텀 강도)
if 'GLD' in df.columns and 'SPY' in df.columns:
    ext_ratios['GLD_SPY'] = ('GLD', 'SPY')   # 금 vs 주식 (공포 헤지, 역방향)

all_ratios = {**base_ratios, **ext_ratios}

for name, (num, den) in all_ratios.items():
    if num in df.columns and den in df.columns:
        valid = df[num].notna() & df[den].notna() & (df[den] != 0)
        df.loc[valid, name] = df.loc[valid, num] / df.loc[valid, den]
        df[f'{name}_50MA']  = df[name].rolling(window=50).mean()
        df[f'{name}_200MA'] = df[name].rolling(window=200).mean()

latest = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# ── 시그널 판별 ────────────────────────────────────────────────────────
risk_on_spy = latest.get('SPY_TLT_50MA', 0)  > latest.get('SPY_TLT_200MA', 0)
risk_on_xly = latest.get('XLY_XLP_50MA', 0)  > latest.get('XLY_XLP_200MA', 0)
risk_on_xlk = latest.get('XLK_XLU_50MA', 0)  > latest.get('XLK_XLU_200MA', 0)
risk_on_brk = latest.get('BRK_SPY_50MA', 1)  < latest.get('BRK_SPY_200MA', 1)  # 역방향

score = sum([risk_on_spy, risk_on_xly, risk_on_xlk, risk_on_brk])

# 확장 신호 (표시용, 점수에는 미포함)
ext_signals = {}
if 'IWM_SPY_50MA' in df.columns:
    ext_signals['IWM_SPY'] = latest.get('IWM_SPY_50MA', 0) > latest.get('IWM_SPY_200MA', 0)
if 'QQQ_SPY_50MA' in df.columns:
    ext_signals['QQQ_SPY'] = latest.get('QQQ_SPY_50MA', 0) > latest.get('QQQ_SPY_200MA', 0)
if 'GLD_SPY_50MA' in df.columns:
    # 금이 주식을 이기면 = 공포 = RISK OFF
    ext_signals['GLD_SPY'] = latest.get('GLD_SPY_50MA', 0) < latest.get('GLD_SPY_200MA', 0)

st.subheader(f"📊 최종 매수/매도 판독기 (기준일: {latest_date})")

if score == 4:
    st.success("🚀 **[FULL ATTACK] 완벽한 대세 상승장입니다.** 스마트 머니가 주식/기술주/소비재로 맹렬하게 쏟아지고 있습니다. 적극 매수하세요.")
elif score == 3:
    st.info("🟢 **[BUY] 좋은 매수 환경입니다.** 시장의 체력이 튼튼합니다. 비중을 늘려도 좋습니다.")
elif score == 2:
    st.warning("🟡 **[HOLD / CAUTION] 시장이 방향을 고민 중입니다.** 공격과 방어가 팽팽합니다. 관망하거나 방어주 비율을 높이세요.")
else:
    st.error("🚨 **[DEFENSE] 하락장 경보 발령!** 스마트 머니가 채권과 방어주로 대피했습니다. 주식을 팔고 현금/채권을 확보하세요.")

st.divider()

# ── 기본 4종 신호 카드 ─────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

def get_status(is_on):
    return "<h3 style='text-align: center; color: #00FF00;'>RISK ON 🟢</h3>" if is_on else \
           "<h3 style='text-align: center; color: #FF4B4B;'>RISK OFF 🔴</h3>"

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

# ── 확장 신호 카드 (데이터 존재 시) ────────────────────────────────────
if ext_signals:
    st.markdown("##### 📡 확장 리스크 지표")
    ecols = st.columns(len(ext_signals))
    labels = {
        'IWM_SPY': ('소형주 강세 (IWM/SPY)', '소형주가 대형주 압도 = 리스크 선호'),
        'QQQ_SPY': ('성장주 모멘텀 (QQQ/SPY)', '나스닥이 시장 선도 = 강세장'),
        'GLD_SPY': ('금 안전자산 (GLD/SPY)', '금 열세 = 공포 없음 (RISK ON)'),
    }
    for i, (key, is_on) in enumerate(ext_signals.items()):
        title, desc = labels.get(key, (key, ''))
        with ecols[i]:
            st.markdown(f"<p style='text-align:center;font-size:0.85em;'><b>{title}</b><br>{desc}</p>", unsafe_allow_html=True)
            st.markdown(get_status(is_on), unsafe_allow_html=True)

st.divider()

# ── 차트: 기본 4종 비율 ────────────────────────────────────────────────
fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    subplot_titles=("SPY / TLT (Stocks vs Bonds)",
                                    "XLY / XLP (Discretionary vs Staples)",
                                    "XLK / XLU (Tech vs Utilities)",
                                    "BRK-B / SPY (Berkshire vs Market)"))

plot_df = df.tail(252 * 2)
colors = ['cyan', 'orange', 'violet', 'lightgreen']
keys   = ['SPY_TLT', 'XLY_XLP', 'XLK_XLU', 'BRK_SPY']

for i, key in enumerate(keys):
    row = i + 1
    if key not in plot_df.columns:
        continue
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[key],
                             name="Ratio", line=dict(color=colors[i], width=1.5)), row=row, col=1)
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_50MA'],
                             name="50MA", line=dict(color='white', width=1.5)), row=row, col=1)
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_200MA'],
                             name="200MA", line=dict(color='gray', width=1.5, dash='dot')), row=row, col=1)

fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified", showlegend=False)
for ann in fig['layout']['annotations']:
    ann['font'] = dict(size=14, color='white')

st.plotly_chart(fig, use_container_width=True)

# ── 확장 차트 (GLD/IWM/QQQ) ────────────────────────────────────────────
ext_chart_keys = [(k, v) for k, v in ext_ratios.items() if k in df.columns]
if ext_chart_keys:
    ext_titles = {
        'IWM_SPY': 'IWM / SPY (소형주 리스크 선호)',
        'QQQ_SPY': 'QQQ / SPY (성장주 모멘텀)',
        'GLD_SPY': 'GLD / SPY (금 vs 주식, 하락=안전)',
    }
    n = len(ext_chart_keys)
    fig2 = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                         subplot_titles=[ext_titles.get(k, k) for k, _ in ext_chart_keys])
    ext_colors = ['gold', 'deepskyblue', 'salmon']
    for i, (key, _) in enumerate(ext_chart_keys):
        row = i + 1
        fig2.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[key],
                                  name=key, line=dict(color=ext_colors[i % 3], width=1.5)), row=row, col=1)
        fig2.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_50MA'],
                                  name="50MA", line=dict(color='white', width=1.5)), row=row, col=1)
        fig2.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df[f'{key}_200MA'],
                                  name="200MA", line=dict(color='gray', width=1.5, dash='dot')), row=row, col=1)
    fig2.update_layout(height=300 * n, template="plotly_dark", hovermode="x unified", showlegend=False)
    for ann in fig2['layout']['annotations']:
        ann['font'] = dict(size=13, color='white')
    with st.expander("📡 확장 리스크 지표 차트", expanded=False):
        st.plotly_chart(fig2, use_container_width=True)

with st.expander("🤖 AI 트레이딩 어시스턴트: 이 4가지 불빛이 의미하는 것 (초보자 가이드)", expanded=True):
    st.markdown("""
    이 화면은 기관 투자자(스마트 머니)들이 **'어느 바구니에 돈을 담고 있는가?'**를 추적하여, 지금 주식을 사도 되는지(RISK ON) 팔아야 하는지(RISK OFF)를 알려줍니다.

    * **1. 시장 중력 (주식 SPY vs 채권 TLT)** — 큰돈이 안전한 채권 대신 주식을 선택했다는 뜻 = 대세 상승 기본 조건
    * **2. 소비 체력 (사치재 XLY vs 필수재 XLP)** — 사람들이 라면 대신 소고기를 먹기 시작 = 실물 경제 건강
    * **3. 공격 본능 (기술주 XLK vs 유틸리티 XLU)** — 성장주로 자금 이동 = 나스닥 강세장
    * **4. 가치 대피소 (BRK.B/SPY)** — 버크셔가 시장을 이기면 위기 신호, 밀리면 건강한 상승장

    **📡 확장 지표:**
    * **IWM/SPY** — 소형주가 대형주를 압도하면 투자자들이 적극적으로 리스크를 감수 중
    * **QQQ/SPY** — 나스닥이 S&P500을 이기면 성장 모멘텀 강함
    * **GLD/SPY** — 금이 주식을 이기면 공포 상태 (RISK OFF 신호)
    """)
