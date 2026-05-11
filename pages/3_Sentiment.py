import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Sentiment & Credit", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

required_cols = ['SP500', 'VIX', 'HY_Spread']
if df.empty or not all(col in df.columns for col in required_cols):
    st.error(f"⚠️ 데이터가 없거나 필수 지표({', '.join(required_cols)})가 누락되었습니다.")
    st.stop()

st.title("🚨 Fear & Credit Risk Monitor")

# ── 지표 계산 ──────────────────────────────────────────────────────────
df['VIX_MA20']  = df['VIX'].rolling(window=20).mean()
df['HY_MA20']   = df['HY_Spread'].rolling(window=20).mean()

# Z-Score (1년 롤링 기준)
roll = 252
df['VIX_ZScore']      = (df['VIX']       - df['VIX'].rolling(roll).mean())      / df['VIX'].rolling(roll).std()
df['HY_ZScore']       = (df['HY_Spread'] - df['HY_Spread'].rolling(roll).mean()) / df['HY_Spread'].rolling(roll).std()

# 백분위 (1년)
df['VIX_Pct']         = df['VIX'].rolling(roll).rank(pct=True) * 100
df['HY_Pct']          = df['HY_Spread'].rolling(roll).rank(pct=True) * 100

recent_df   = df.tail(5)
latest      = df.iloc[-1]
prev        = df.iloc[-2]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# ── 시그널 ─────────────────────────────────────────────────────────────
vix_panic        = bool((recent_df['VIX'] >= 30).any())
vix_capitulation = vix_panic and bool(latest['VIX'] < prev['VIX'])
credit_stress    = bool(latest['HY_Spread'] >= 5.0)

# 확장 신호
vix_z    = latest['VIX_ZScore']   if pd.notna(latest.get('VIX_ZScore'))   else 0
hy_z     = latest['HY_ZScore']    if pd.notna(latest.get('HY_ZScore'))    else 0
vix_pct  = latest['VIX_Pct']      if pd.notna(latest.get('VIX_Pct'))      else 50
hy_pct   = latest['HY_Pct']       if pd.notna(latest.get('HY_Pct'))       else 50

# 극단적 공포 (Z > 2, 역사적 상위 2%)
extreme_fear     = vix_z > 2.0
# 신용 극단 위기 (Z > 2)
extreme_credit   = hy_z  > 2.0
# 역발상 기회: VIX 극단 공포 + HY 정상 = 일시적 패닉일 가능성
contrarian_buy   = extreme_fear and not extreme_credit

# ── UI ─────────────────────────────────────────────────────────────────
st.subheader(f"📊 Market Psychology (기준일: {latest_date})")

col1, col2, col3 = st.columns(3)

def status_ui(is_on, on_text, off_text, color_on="#FF4B4B", color_off="#00FF00"):
    color = color_on if is_on else color_off
    return f"<h3 style='text-align: center; color: {color};'>{on_text if is_on else off_text}</h3>"

with col1:
    st.markdown("<p style='text-align: center;'><b>공포 지수 (VIX)</b><br>최근 30 이상 돌파</p>", unsafe_allow_html=True)
    st.markdown(status_ui(vix_panic, "PANIC 🔥", "NORMAL 🟢"), unsafe_allow_html=True)
with col2:
    st.markdown("<p style='text-align: center;'><b>⭐ 시장 항복 (Capitulation)</b><br>VIX 30 도달 후 하락 전환</p>", unsafe_allow_html=True)
    st.markdown(status_ui(vix_capitulation, "BUY SIGNAL 🟢", "WAIT ⚪", "#00FF00", "#888888"), unsafe_allow_html=True)
with col3:
    st.markdown("<p style='text-align: center;'><b>신용 경색 (HY Spread)</b><br>스프레드 5.0% 이상</p>", unsafe_allow_html=True)
    st.markdown(status_ui(credit_stress, "STRESS 🚨", "SAFE 🟢"), unsafe_allow_html=True)

st.divider()

# ── Z-Score & 백분위 카드 ──────────────────────────────────────────────
st.markdown("##### 📐 역사적 극단 수치 (Z-Score & 백분위)")

mc1, mc2, mc3, mc4 = st.columns(4)

def zscore_color(z):
    if z > 2:  return "#FF4B4B"
    if z > 1:  return "#FFC107"
    if z < -1: return "#00FF00"
    return "#aaaaaa"

def pct_color(p):
    if p > 90: return "#FF4B4B"
    if p > 70: return "#FFC107"
    if p < 20: return "#00FF00"
    return "#aaaaaa"

with mc1:
    vc = zscore_color(vix_z)
    st.markdown(f"<div style='text-align:center;border:1px solid #444;border-radius:8px;padding:10px;'>"
                f"<p style='margin:0;color:#aaa;font-size:0.85em;'>VIX Z-Score</p>"
                f"<h2 style='margin:4px 0;color:{vc};'>{vix_z:+.2f}</h2>"
                f"<p style='margin:0;font-size:0.75em;color:#888;'>|Z|>2 = 역사적 극단</p></div>",
                unsafe_allow_html=True)
with mc2:
    vpc = pct_color(vix_pct)
    st.markdown(f"<div style='text-align:center;border:1px solid #444;border-radius:8px;padding:10px;'>"
                f"<p style='margin:0;color:#aaa;font-size:0.85em;'>VIX 백분위</p>"
                f"<h2 style='margin:4px 0;color:{vpc};'>{vix_pct:.0f}%ile</h2>"
                f"<p style='margin:0;font-size:0.75em;color:#888;'>1년 대비 상위 몇 %</p></div>",
                unsafe_allow_html=True)
with mc3:
    hc = zscore_color(hy_z)
    st.markdown(f"<div style='text-align:center;border:1px solid #444;border-radius:8px;padding:10px;'>"
                f"<p style='margin:0;color:#aaa;font-size:0.85em;'>HY Spread Z-Score</p>"
                f"<h2 style='margin:4px 0;color:{hc};'>{hy_z:+.2f}</h2>"
                f"<p style='margin:0;font-size:0.75em;color:#888;'>|Z|>2 = 신용 극단 위기</p></div>",
                unsafe_allow_html=True)
with mc4:
    hpc = pct_color(hy_pct)
    st.markdown(f"<div style='text-align:center;border:1px solid #444;border-radius:8px;padding:10px;'>"
                f"<p style='margin:0;color:#aaa;font-size:0.85em;'>HY Spread 백분위</p>"
                f"<h2 style='margin:4px 0;color:{hpc};'>{hy_pct:.0f}%ile</h2>"
                f"<p style='margin:0;font-size:0.75em;color:#888;'>1년 대비 상위 몇 %</p></div>",
                unsafe_allow_html=True)

if contrarian_buy:
    st.success("🎯 **역발상 매수 기회:** VIX가 역사적 극단이지만 신용은 정상 → 일시적 패닉 셀링 가능성. 항복 신호와 함께라면 강한 반등 타점.")
elif extreme_credit and extreme_fear:
    st.error("🚨 **이중 위기 경보:** VIX + 신용 모두 역사적 극단. 2008, 2020 수준의 위기. 포지션 최소화.")
elif extreme_credit:
    st.warning("⚠️ **신용 극단 경보:** HY Spread가 역사적 상위 2%. 실물 경제 위기 가능성 — 주식 비중 축소.")

st.divider()

# ── 차트 ──────────────────────────────────────────────────────────────
fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                    vertical_spacing=0.06,
                    row_heights=[0.35, 0.22, 0.22, 0.21],
                    subplot_titles=("📈 S&P 500 Price",
                                    "😨 VIX (Volatility Index)",
                                    "🏦 High Yield Spread (Credit Risk)",
                                    "📐 Z-Score (역사적 극단 감지)"))

plot_df = df.tail(252 * 3)

# Row 1: S&P 500
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'],
                         name="S&P 500", line=dict(color='white', width=2)), row=1, col=1)

# Row 2: VIX
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['VIX'],
                         name="VIX", line=dict(color='orange', width=1.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['VIX_MA20'],
                         name="VIX 20MA", line=dict(color='yellow', width=1, dash='dot')), row=2, col=1)
fig.add_hline(y=30, line_width=1.5, line_dash="dash", line_color="red",
              annotation_text="Panic (30)", annotation_position="top left", row=2, col=1)
fig.add_hline(y=20, line_width=1,   line_dash="dash", line_color="gray",
              annotation_text="Normal (20)", annotation_position="bottom left", row=2, col=1)

# Row 3: HY Spread
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['HY_Spread'],
                         name="HY Spread", line=dict(color='cyan', width=1.5)), row=3, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['HY_MA20'],
                         name="Spread 20MA", line=dict(color='lightblue', width=1, dash='dot')), row=3, col=1)
fig.add_hline(y=5.0, line_width=1.5, line_dash="dash", line_color="red",
              annotation_text="Stress (5.0%)", annotation_position="top left", row=3, col=1)

# Row 4: Z-Score
if 'VIX_ZScore' in plot_df.columns:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['VIX_ZScore'],
                             name="VIX Z", line=dict(color='orange', width=1.5)), row=4, col=1)
if 'HY_ZScore' in plot_df.columns:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['HY_ZScore'],
                             name="HY Z", line=dict(color='cyan', width=1.5)), row=4, col=1)
fig.add_hline(y=2,  line_width=1, line_dash="dash", line_color="red",   row=4, col=1)
fig.add_hline(y=-2, line_width=1, line_dash="dash", line_color="green", row=4, col=1)
fig.add_hline(y=0,  line_width=1, line_dash="dot",  line_color="gray",  row=4, col=1)

fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified",
                  showlegend=True,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
for ann in fig['layout']['annotations']:
    ann['font'] = dict(size=15, color='white')

st.plotly_chart(fig, use_container_width=True)

with st.expander("🤖 AI 트레이딩 어시스턴트: 공포와 신용 지표 활용법", expanded=True):
    st.markdown("""
    * **🔥 공포 지수 (VIX 30 돌파):** 패닉 셀링 = 매수 준비 구간. 역사적으로 VIX 30+ 구간 진입 후 1년 수익률 압도적.
    * **🟢 시장 항복 (Capitulation):** VIX 30 찍고 꺾이는 순간 = 가장 안전한 단기 바닥 타점.
    * **🚨 신용 경색 (HY Spread 5%):** 은행권 돈줄 막힘 = 경제 위기 신호. 주식 비중 최소화.

    **📐 Z-Score 활용법:**
    * Z > +2: 지표가 역사적 상위 2% 수준의 극단값 → 반전 가능성 높음 (VIX면 매수, HY면 매도 경계)
    * Z < -2: 역사적 하위 2% 수준 → 안심 구간 (VIX 낮음 = 공포 없음, HY 낮음 = 신용 건강)
    * **역발상 기회:** VIX Z-Score가 극단이지만 HY가 정상이면, 진짜 위기가 아닌 일시적 패닉. 역대 최고의 매수 타점 중 하나.
    """)
