import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Sentiment & Credit", layout="wide")


# 1. 데이터 로드
@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

# 필수 지표 확인
required_cols = ['SP500', 'VIX', 'HY_Spread']
if df.empty or not all(col in df.columns for col in required_cols):
    st.error(f"⚠️ 데이터가 없거나 필수 지표({', '.join(required_cols)})가 누락되었습니다. 메인 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("🚨 Fear & Credit Risk Monitor")

# 2. 지표 분석 엔진
# VIX 및 HY_Spread의 20일(약 1개월) 이동평균 산출 (추세 확인용)
df['VIX_MA20'] = df['VIX'].rolling(window=20).mean()
df['HY_MA20'] = df['HY_Spread'].rolling(window=20).mean()

recent_df = df.tail(5)
latest = df.iloc[-1]
prev = df.iloc[-2]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# [조건 1] VIX 극단적 공포 (최근 5일 내 VIX 30 이상 도달)
vix_panic = (recent_df['VIX'] >= 30).any()

# [조건 2] VIX 항복 (Capitulation): 공포가 30을 찍고 꺾이는 시점 (진정한 매수 타점)
vix_capitulation = vix_panic and (latest['VIX'] < prev['VIX'])

# [조건 3] 신용 경색 (High Yield Spread 5.0% 초과)
credit_stress = latest['HY_Spread'] >= 5.0

# 3. 대시보드 UI (시그널 상태창)
st.subheader(f"📊 Market Psychology (기준일: {latest_date})")

col1, col2, col3 = st.columns(3)


def status_ui(is_on, on_text, off_text, color_on="#FF4B4B", color_off="#00FF00"):
    # 공포/위험 지표이므로 켜졌을 때 빨간색(위험) 또는 주황색 계열을 기본으로 하되,
    # '항복(매수 기회)' 시그널은 초록색으로 표시합니다.
    color = color_on if is_on else color_off
    return f"<h3 style='text-align: center; color: {color};'>{on_text if is_on else off_text}</h3>"


with col1:
    st.markdown("<p style='text-align: center;'><b>공포 지수 (VIX)</b><br>최근 30 이상 돌파</p>", unsafe_allow_html=True)
    st.markdown(status_ui(vix_panic, "PANIC 🔥", "NORMAL 🟢", "#FF4B4B", "#00FF00"), unsafe_allow_html=True)
with col2:
    st.markdown("<p style='text-align: center;'><b>⭐ 시장 항복 (Capitulation)</b><br>VIX 30 도달 후 하락 전환</p>",
                unsafe_allow_html=True)
    # 항복 시그널은 주식을 사야 하는 '좋은' 신호이므로 켜졌을 때 초록색
    st.markdown(status_ui(vix_capitulation, "BUY SIGNAL 🟢", "WAIT ⚪", "#00FF00", "#888888"), unsafe_allow_html=True)
with col3:
    st.markdown("<p style='text-align: center;'><b>신용 경색 (HY Spread)</b><br>스프레드 5.0% 이상</p>", unsafe_allow_html=True)
    st.markdown(status_ui(credit_stress, "STRESS 🚨", "SAFE 🟢", "#FF4B4B", "#00FF00"), unsafe_allow_html=True)

st.divider()


# 5. 차트 시각화
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    vertical_spacing=0.07,
                    row_heights=[0.4, 0.3, 0.3],
                    subplot_titles=("📈 S&P 500 Price", "😨 VIX (Volatility Index)", "🏦 High Yield Spread (Credit Risk)"))

plot_df = df.tail(252 * 3)  # 거시 지표는 사이클이 길어 최근 3년 치를 기본으로 표출

# [Row 1] 가격
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'], name="S&P 500", line=dict(color='white', width=2)),
              row=1, col=1)

# [Row 2] VIX
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['VIX'], name="VIX", line=dict(color='orange', width=1.5)), row=2,
              col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['VIX_MA20'], name="VIX 20MA",
                         line=dict(color='yellow', width=1, dash='dot')), row=2, col=1)
# 기준선 추가
fig.add_hline(y=30, line_width=1.5, line_dash="dash", line_color="red", annotation_text="Panic (30)",
              annotation_position="top left", row=2, col=1)
fig.add_hline(y=20, line_width=1, line_dash="dash", line_color="gray", annotation_text="Normal (20)",
              annotation_position="bottom left", row=2, col=1)

# [Row 3] HY Spread
fig.add_trace(
    go.Scatter(x=plot_df['Date'], y=plot_df['HY_Spread'], name="HY Spread", line=dict(color='cyan', width=1.5)), row=3,
    col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['HY_MA20'], name="Spread 20MA",
                         line=dict(color='lightblue', width=1, dash='dot')), row=3, col=1)
# 기준선 추가
fig.add_hline(y=5.0, line_width=1.5, line_dash="dash", line_color="red", annotation_text="Stress Level (5.0%)",
              annotation_position="top left", row=3, col=1)

fig.update_layout(height=900, template="plotly_dark", hovermode="x unified",
                  showlegend=True,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

for i in fig['layout']['annotations']:
    i['font'] = dict(size=16, color='white')

st.plotly_chart(fig, use_container_width=True)

# 4. AI 해설 영역
with st.expander("🤖 AI 트레이딩 어시스턴트: 공포와 신용 지표 활용법", expanded=True):
    st.markdown("""
    이 화면은 주식 시장의 겉모습(가격)이 아닌, **투자자들의 심리와 자금의 숨은 흐름**을 보여줍니다.

    * **🔥 공포 지수 (VIX 30 돌파): "피가 낭자할 때가 기회다"**
        * VIX가 30을 넘었다는 것은 시장 참여자들이 이성적인 판단을 잃고 주식을 패닉 셀링(투매)하고 있다는 뜻입니다. 
        * 역사적으로 VIX 30 이상 구간에서 주식을 모아갔을 때의 1년 뒤 승률은 압도적으로 높습니다.
    * **🟢 시장 항복 (Capitulation): "소나기가 그치기 시작하는 찰나"**
        * VIX가 단순히 높은 것보다, **30을 찍고 내려오기 시작하는 순간**이 가장 안전한 단기 바닥입니다. 투매가 끝나고 숏 커버링(공매도 상환)이 들어오며 급반등이 시작되는 자리입니다.
    * **🚨 신용 경색 (하이일드 스프레드): "탄광 속의 카나리아"**
        * 신용도가 낮은 기업들이 돈을 빌릴 때 얹어주는 웃돈(가산금리)입니다. 
        * 이 수치가 **5.0%**를 넘어가면 은행들이 기업에 돈을 빌려주는 것을 극도로 꺼리고 있다는 뜻입니다. 즉, "진짜 경제 위기"가 오고 있다는 강력한 경고등이므로 주식 비중을 줄이고 현금을 확보해야 합니다.
    """)
