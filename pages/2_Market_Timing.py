import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Market Timing", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty or 'SP500' not in df.columns:
    st.error("⚠️ 데이터가 없거나 S&P 500 데이터가 누락되었습니다. 메인 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("🎯 Tactical Buy Signal (S&P 500)")

# ── 지표 계산 ──────────────────────────────────────────────────────────
df['SMA_50']  = df['SP500'].rolling(window=50).mean()
df['SMA_200'] = df['SP500'].rolling(window=200).mean()

# RSI (14일)
delta = df['SP500'].diff()
gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
loss  = -1 * delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
df['RSI'] = 100 - (100 / (1 + gain / loss))

# MACD
df['MACD']   = df['SP500'].ewm(span=12, adjust=False).mean() - df['SP500'].ewm(span=26, adjust=False).mean()
df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

# Stochastic RSI (14, 3, 3)
rsi_min = df['RSI'].rolling(14).min()
rsi_max = df['RSI'].rolling(14).max()
stoch_rsi_raw = (df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9) * 100
df['StochRSI_K'] = stoch_rsi_raw.rolling(3).mean()
df['StochRSI_D'] = df['StochRSI_K'].rolling(3).mean()

# 시장 레짐 (50MA vs 200MA + VIX)
vix_val = df['VIX'].iloc[-1] if 'VIX' in df.columns else 20
sma50_v  = df['SMA_50'].iloc[-1]
sma200_v = df['SMA_200'].iloc[-1]

if sma50_v > sma200_v and vix_val < 25:
    regime_label = "🟢 BULL"
    regime_color = "#00FF00"
elif sma50_v < sma200_v or vix_val > 30:
    regime_label = "🔴 BEAR"
    regime_color = "#FF4B4B"
else:
    regime_label = "🟡 TRANSITION"
    regime_color = "#FFC107"

recent_df = df.tail(5)
latest    = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# ── 시그널 판정 ────────────────────────────────────────────────────────
ma_golden_cross = ((recent_df['SMA_50'] > recent_df['SMA_200']) &
                   (recent_df['SMA_50'].shift(1) <= recent_df['SMA_200'].shift(1)))
ma_on = bool((latest['SP500'] > latest['SMA_200']) and ma_golden_cross.any())

rsi_cross_up = ((recent_df['RSI'] > 30) & (recent_df['RSI'].shift(1) <= 30))
rsi_on = bool(rsi_cross_up.any())

macd_cross_up = ((recent_df['MACD'] < 0) &
                 (recent_df['MACD'] > recent_df['Signal']) &
                 (recent_df['MACD'].shift(1) <= recent_df['Signal'].shift(1)))
macd_on = bool(macd_cross_up.any())

div_window = df.tail(60)
half = len(div_window) // 2
older_half, newer_half = div_window.iloc[:half], div_window.iloc[half:]
divergence_on = bool(
    (newer_half['SP500'].min() < older_half['SP500'].min()) and
    (newer_half['RSI'].min()   > older_half['RSI'].min())   and
    (newer_half['RSI'].min()   < 40)
)

# Stochastic RSI 과매도 반등 (K < 20 → 20 상향 돌파)
stoch_cross = ((recent_df['StochRSI_K'] > 20) & (recent_df['StochRSI_K'].shift(1) <= 20))
stoch_on = bool(stoch_cross.any() and latest['StochRSI_K'] < 50)

# 레짐 필터: BEAR 레짐에서는 추세 추종 신호(MA, MACD)를 비활성화
if regime_label == "🔴 BEAR":
    ma_on   = False
    macd_on = False

# ── 대시보드 UI ────────────────────────────────────────────────────────
st.markdown(
    f"<div style='display:inline-block;background:rgba(255,255,255,0.05);"
    f"border-radius:6px;padding:6px 14px;margin-bottom:12px;'>"
    f"<b>현재 레짐:</b> <span style='color:{regime_color};font-weight:bold;'>{regime_label}</span>"
    f"{'&nbsp;&nbsp;<span style=\"color:#FFC107;font-size:0.85em;\">⚠️ BEAR 레짐: 추세 신호 비활성화</span>' if regime_label == '🔴 BEAR' else ''}"
    f"</div>",
    unsafe_allow_html=True
)

st.subheader(f"📊 Signal Status (기준일: {latest_date})")

col1, col2, col3, col4, col5 = st.columns(5)

def status_ui(is_on, on_text="ON 🟢", off_text="OFF 🔴"):
    color = "#00FF00" if is_on else "#FF4B4B"
    return f"<h3 style='text-align: center; color: {color};'>{on_text if is_on else off_text}</h3>"

with col1:
    st.markdown("<p style='text-align: center;'><b>추세 (MA)</b><br>50/200 골든크로스</p>", unsafe_allow_html=True)
    st.markdown(status_ui(ma_on), unsafe_allow_html=True)
with col2:
    st.markdown("<p style='text-align: center;'><b>모멘텀 (RSI)</b><br>30 상향 돌파</p>", unsafe_allow_html=True)
    st.markdown(status_ui(rsi_on), unsafe_allow_html=True)
with col3:
    st.markdown("<p style='text-align: center;'><b>전환 (MACD)</b><br>0 이하 시그널 교차</p>", unsafe_allow_html=True)
    st.markdown(status_ui(macd_on), unsafe_allow_html=True)
with col4:
    st.markdown("<p style='text-align: center;'><b>⚠️ 상승 다이버전스</b><br>가격↓ RSI↑</p>", unsafe_allow_html=True)
    st.markdown(status_ui(divergence_on, "DETECTED 🔥", "NONE ⚪"), unsafe_allow_html=True)
with col5:
    st.markdown("<p style='text-align: center;'><b>⚡ Stoch RSI</b><br>과매도 반등 감지</p>", unsafe_allow_html=True)
    st.markdown(status_ui(stoch_on, "BOUNCE 🟢", "WAIT ⚪"), unsafe_allow_html=True)

st.divider()

# ── 차트 ──────────────────────────────────────────────────────────────
fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                    vertical_spacing=0.06,
                    row_heights=[0.45, 0.2, 0.18, 0.17],
                    subplot_titles=("📈 Price & Moving Average",
                                    "🔄 Trend Reversal (MACD)",
                                    "⚡ Momentum (RSI)",
                                    "🎯 Stochastic RSI"))

plot_df = df.tail(252)

# Row 1: 가격 + MA
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'],
                         name="S&P 500", line=dict(color='white', width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMA_50'],
                         name="50일선", line=dict(color='yellow', width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMA_200'],
                         name="200일선", line=dict(color='magenta', width=1.5)), row=1, col=1)

# Row 2: MACD
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['MACD'],
                         name="MACD", line=dict(color='cyan', width=1.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Signal'],
                         name="Signal", line=dict(color='orange', width=1.5, dash='dot')), row=2, col=1)
fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray", row=2, col=1)

# Row 3: RSI
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['RSI'],
                         name="RSI", line=dict(color='violet', width=1.5)), row=3, col=1)
fig.add_hline(y=70, line_width=1, line_dash="dash", line_color="red",   row=3, col=1)
fig.add_hline(y=30, line_width=1, line_dash="dash", line_color="green", row=3, col=1)

# Row 4: Stochastic RSI
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['StochRSI_K'],
                         name="Stoch K", line=dict(color='lime', width=1.5)), row=4, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['StochRSI_D'],
                         name="Stoch D", line=dict(color='red', width=1.5, dash='dot')), row=4, col=1)
fig.add_hline(y=80, line_width=1, line_dash="dash", line_color="red",   row=4, col=1)
fig.add_hline(y=20, line_width=1, line_dash="dash", line_color="green", row=4, col=1)

fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified",
                  showlegend=True,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
for ann in fig['layout']['annotations']:
    ann['font'] = dict(size=16, color='white')

st.plotly_chart(fig, use_container_width=True)

with st.expander("🤖 AI 트레이딩 어시스턴트: 각 시그널 해설", expanded=True):
    st.markdown("""
    * **📈 추세 (MA 골든크로스):** 50일선이 200일선을 뚫고 올라가는 순간 = 대세 상승 시작 신호. ⚠️ BEAR 레짐에서는 자동 비활성화(거짓 신호 방지).
    * **📉 모멘텀 (RSI 30 상향 돌파):** 극단적 공포 이후 회복 = 낙폭 과대 해소 타점.
    * **🔄 전환 (MACD 0 이하 교차):** 하락력 약화 + 상승력 강화 = 반등 초입. ⚠️ BEAR 레짐에서 비활성화.
    * **🔥 상승 다이버전스:** 가격은 더 내려갔지만 RSI는 더 높은 저점 = 매도 세력 소진.
    * **⚡ Stochastic RSI:** RSI의 RSI — 일반 RSI보다 2~5일 빠르게 반등을 감지. K선이 20 아래에서 상향 돌파 시 단기 매수.
    """)
