import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Market Timing", layout="wide")

# 1. 데이터 로드
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

# 2. 지표 계산 엔진
df['SMA_50'] = df['SP500'].rolling(window=50).mean()
df['SMA_200'] = df['SP500'].rolling(window=200).mean()

delta = df['SP500'].diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
loss = -1 * delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

exp1 = df['SP500'].ewm(span=12, adjust=False).mean()
exp2 = df['SP500'].ewm(span=26, adjust=False).mean()
df['MACD'] = exp1 - exp2
df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

recent_df = df.tail(5)
latest = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# 시그널 판정
ma_golden_cross = (recent_df['SMA_50'] > recent_df['SMA_200']) & (recent_df['SMA_50'].shift(1) <= recent_df['SMA_200'].shift(1))
ma_on = (latest['SP500'] > latest['SMA_200']) and ma_golden_cross.any()

rsi_cross_up = (recent_df['RSI'] > 30) & (recent_df['RSI'].shift(1) <= 30)
rsi_on = rsi_cross_up.any()

macd_cross_up = (recent_df['MACD'] < 0) & (recent_df['MACD'] > recent_df['Signal']) & (recent_df['MACD'].shift(1) <= recent_df['Signal'].shift(1))
macd_on = macd_cross_up.any()

div_window = df.tail(60)
half = len(div_window) // 2
older_half = div_window.iloc[:half]
newer_half = div_window.iloc[half:]
older_price_low, older_rsi_low = older_half['SP500'].min(), older_half['RSI'].min()
newer_price_low, newer_rsi_low = newer_half['SP500'].min(), newer_half['RSI'].min()
divergence_on = (newer_price_low < older_price_low) and (newer_rsi_low > older_rsi_low) and (newer_rsi_low < 40)

# 3. 대시보드 UI (시그널 상태창)
st.subheader(f"📊 Signal Status (기준일: {latest_date})")
col1, col2, col3, col4 = st.columns(4)

def status_ui(is_on, on_text="ON 🟢", off_text="OFF 🔴"):
    return f"<h3 style='text-align: center; color: {'#00FF00' if is_on else '#FF4B4B'};'>{on_text if is_on else off_text}</h3>"

with col1:
    st.markdown("<p style='text-align: center;'><b>추세 (MA)</b><br>50/200 골든크로</p>", unsafe_allow_html=True)
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

st.divider()

# 5. 차트 시각화 (그래프별 이름 추가)
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    vertical_spacing=0.07, # 간격을 조금 더 넓혀서 가독성 확보
                    row_heights=[0.5, 0.25, 0.25],
                    subplot_titles=("📈 Price & Moving Average", "🔄 Trend Reversal (MACD)", "⚡ Momentum (RSI)"))

plot_df = df.tail(252)

# [Row 1] 가격 및 이동평균
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'], name="S&P 500", line=dict(color='white', width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMA_50'], name="50일선", line=dict(color='yellow', width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMA_200'], name="200일선", line=dict(color='magenta', width=1.5)), row=1, col=1)

# [Row 2] MACD
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['MACD'], name="MACD", line=dict(color='cyan', width=1.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Signal'], name="Signal", line=dict(color='orange', width=1.5, dash='dot')), row=2, col=1)
fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray", row=2, col=1)

# [Row 3] RSI
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['RSI'], name="RSI", line=dict(color='violet', width=1.5)), row=3, col=1)
fig.add_hline(y=70, line_width=1, line_dash="dash", line_color="red", row=3, col=1)
fig.add_hline(y=30, line_width=1, line_dash="dash", line_color="green", row=3, col=1)

# 레이아웃 조정 및 타이틀 위치 미세조정
fig.update_layout(height=900, template="plotly_dark", hovermode="x unified",
                  showlegend=True, # 범례를 켜서 색상별 의미 파악 가능하게 함
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

# 서브플롯 타이틀 폰트 크기 조정
for i in fig['layout']['annotations']:
    i['font'] = dict(size=18, color='white')

st.plotly_chart(fig, use_container_width=True)

# ⭐ 4. AI 트레이딩 어시스턴트 해설 영역 (새로 추가됨)
with st.expander("🤖 AI 트레이딩 어시스턴트: 각 시그널이 'ON'일 때 매수해야 하는 이유", expanded=True):
    st.markdown("""
    초보자를 위한 시그널 해석 가이드입니다. 불빛이 🟢 **ON**으로 바뀌었다면 아래의 이유로 매수 확률이 높아진 것입니다.

    * **📈 추세 (MA 골든크로스): "계절이 겨울에서 봄으로 바뀌는 시점"**
        * 단기(50일) 평균선이 장기(200일) 평균선을 뚫고 올라가는 현상입니다. 
        * **왜 사야 할까?** 거대한 기관 자금들이 하락장을 끝내고 주식을 본격적으로 사모으기 시작했다는 가장 확실한 증거입니다. 대세 상승장의 초입일 확률이 높습니다.
    * **📉 모멘텀 (RSI 30 상향 돌파): "고무줄이 팽팽하게 당겨졌다가 튕겨 오르는 시점"**
        * RSI가 30 이하로 떨어졌다는 건 시장에 공포가 극에 달해 사람들이 주식을 '비이성적으로 던졌다'는 뜻입니다.
        * **왜 사야 할까?** 악재가 다 반영되어 더 이상 팔 사람이 없을 때 30을 뚫고 올라옵니다. 가장 싸게 주울 수 있는 '줍줍' 타이밍입니다.
    * **🔄 전환 (MACD 0 이하 교차): "하락하던 차가 브레이크를 밟고 다시 엑셀을 밟는 시점"**
        * 주가가 아직 바닥권(0선 아래)에 있지만, 하락하는 힘이 약해지고 상승하는 힘이 강해지는 교차점입니다.
        * **왜 사야 할까?** 눈에 띄는 큰 반등이 나오기 직전에 남들보다 반 박자 빠르게 매수할 수 있는 기회를 줍니다.
    * **🔥 상승 다이버전스 (보너스): "숨겨진 폭등의 전조증상"**
        * 주가는 이전보다 더 떨어졌는데, 보조지표(RSI)의 저점은 오히려 높아지는 기현상입니다.
        * **왜 사야 할까?** 겉으로는 주가가 떨어져서 망한 것 같지만, 속으로는 '매도 세력'이 완전히 지쳐버렸다는 것을 의미합니다. 조만간 강력한 급반등이 나올 확률이 매우 높습니다.
    """)