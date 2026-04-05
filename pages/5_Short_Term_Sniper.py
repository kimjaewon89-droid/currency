import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Short-Term Sniper", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty or 'SP500' not in df.columns:
    st.error("⚠️ 데이터가 없습니다. 홈 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("🔫 Short-Term Sniper (단기 타점 포착)")

# 1. 지표 계산 엔진
# [볼린저 밴드] 20일 이동평균 기준, 표준편차 2배
df['SMA_20'] = df['SP500'].rolling(window=20).mean()
df['STD_20'] = df['SP500'].rolling(window=20).std()
df['BB_Upper'] = df['SMA_20'] + (df['STD_20'] * 2)
df['BB_Lower'] = df['SMA_20'] - (df['STD_20'] * 2)

# [단기 이격도] 5일선 기준 (현재가 / 5일선 * 100)
df['SMA_5'] = df['SP500'].rolling(window=5).mean()
df['Disparity_5'] = (df['SP500'] / df['SMA_5']) * 100

latest = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# 2. 시그널 판별
# 볼린저 하단 터치 (매수) / 상단 터치 (매도)
bb_buy = latest['SP500'] <= latest['BB_Lower']
bb_sell = latest['SP500'] >= latest['BB_Upper']

# 이격도 과매도 (매수, 지수 기준 99% 이하) / 과매수 (매도, 101% 이상)
disp_buy = latest['Disparity_5'] <= 99.0
disp_sell = latest['Disparity_5'] >= 101.0

st.subheader(f"⚡ Today's Action Signal (기준일: {latest_date})")

col1, col2 = st.columns(2)


def sniper_ui(buy_on, sell_on, indicator_name, buy_desc, sell_desc):
    if buy_on:
        status = "<h3 style='color: #00FF00;'>🟢 BUY NOW (저점 매수)</h3>"
        desc = buy_desc
    elif sell_on:
        status = "<h3 style='color: #FF4B4B;'>🔴 SELL NOW (단기 매도)</h3>"
        desc = sell_desc
    else:
        status = "<h3 style='color: #888888;'>⚪ WAIT (관망)</h3>"
        desc = "현재는 중간 지대에 있습니다. 무리하게 진입하지 마세요."

    return f"""
    <div style="border:1px solid #444; border-radius:10px; padding:20px; text-align:center; height: 180px;">
        <h4>{indicator_name}</h4>
        {status}
        <p style='font-size: 0.9em; color: #BBB;'>{desc}</p>
    </div>
    """


with col1:
    st.markdown(sniper_ui(
        bb_buy, bb_sell,
        "1. 볼린저 밴드 (고무줄 극한 타점)",
        "주가가 하단 밴드를 강하게 터치했습니다. 단기 급반등이 예상됩니다.",
        "주가가 상단 밴드에 부딪혔습니다. 단기 조정을 주의하고 수익을 실현하세요."
    ), unsafe_allow_html=True)

with col2:
    st.markdown(sniper_ui(
        disp_buy, disp_sell,
        "2. 5일 이격도 (단기 낙폭/급등 폭)",
        "5일 평균선 대비 과도하게 하락했습니다. '낙폭 과대'에 의한 기술적 반등 자리입니다.",
        "5일선 대비 단기 급등했습니다. 과열 상태이니 신규 매수는 멈추세요."
    ), unsafe_allow_html=True)

st.divider()

# 3. 차트 시각화
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                    row_heights=[0.7, 0.3],
                    subplot_titles=("📈 볼린저 밴드 (Bollinger Bands)", "⚡ 5일 이격도 (Disparity Index)"))

# 단기 매매이므로 최근 6개월(120일)만 확대해서 봅니다.
plot_df = df.tail(120)

# [Row 1] 볼린저 밴드
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['BB_Upper'], line=dict(color='gray', width=1, dash='dash'),
                         name='Upper Band'), row=1, col=1)
fig.add_trace(
    go.Scatter(x=plot_df['Date'], y=plot_df['BB_Lower'], line=dict(color='gray', width=1, dash='dash'), fill='tonexty',
               fillcolor='rgba(128,128,128,0.1)', name='Lower Band'), row=1, col=1)
fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'], line=dict(color='white', width=2), name='S&P 500'),
              row=1, col=1)
fig.add_trace(
    go.Scatter(x=plot_df['Date'], y=plot_df['SMA_20'], line=dict(color='orange', width=1.5), name='20MA (중심선)'), row=1,
    col=1)

# [Row 2] 이격도
fig.add_trace(
    go.Scatter(x=plot_df['Date'], y=plot_df['Disparity_5'], line=dict(color='cyan', width=1.5), name='5-Day Disparity'),
    row=2, col=1)
fig.add_hline(y=100, line_width=1, line_dash="dash", line_color="yellow", row=2, col=1)
fig.add_hline(y=101, line_width=1, line_dash="dot", line_color="red", annotation_text="Sell Zone (101)", row=2, col=1)
fig.add_hline(y=99, line_width=1, line_dash="dot", line_color="green", annotation_text="Buy Zone (99)", row=2, col=1)

fig.update_layout(height=800, template="plotly_dark", hovermode="x unified", showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# 4. AI 트레이딩 어시스턴트: 단기 타점 정밀 해설
with st.expander("🤖 AI 트레이딩 어시스턴트: 단기 저격용 지표 정밀 해설 (필독)", expanded=True):
    st.markdown("""
    거시적 흐름이 '상승장'일 때, 아래 두 지표가 🟢 **BUY** 신호를 보낸다면 그것은 **'달리는 말의 일시적인 쉼표'**를 포착한 것입니다.

    ---

    ### 1️⃣ 볼린저 밴드 (Bollinger Bands): "주가의 안전 울타리"
    * **개념:** 주가가 이동평균선을 중심으로 위아래 일정한 폭(표준편차) 안에서만 움직인다는 통계학적 원리를 이용합니다. 주가의 **95.4%**는 이 밴드 안에서 움직입니다.
    * **왜 사야 할까? (하단 터치 시):** 주가가 하단 밴드를 뚫고 나갔다는 것은 통계적으로 **발생할 확률이 5%도 안 되는 '비정상적인 과매도'** 상태라는 뜻입니다. 팽팽하게 당겨진 고무줄이 제자리로 돌아오려는 성질처럼, 주가는 다시 밴드 안쪽(중심선)으로 강하게 튕겨 올라올 가능성이 매우 높습니다.
    * **주의사항:** 강력한 악재로 인해 밴드 하단을 타고 계속 내려가는 '밴드 타기' 현상이 나올 수 있습니다. 이때는 반드시 **이격도**와 함께 확인해야 합니다.

    ---

    ### 2️⃣ 5일 이격도 (Disparity Index): "단기 과속 단속 카메라"
    * **개념:** 현재 주가가 5일 동안의 평균 가격과 얼마나 떨어져 있는지를 수치화한 것입니다. (100%면 평균과 일치, 105%면 평균보다 5% 비싸다는 뜻)
    * **왜 사야 할까? (99% 이하 시):** 지수(S&P 500)는 개별 종목과 달리 덩치가 커서 5일 평균에서 1% 이상 멀어지는 일이 흔치 않습니다. 이격도가 99% 밑으로 떨어졌다는 건, **단기적으로 너무 빠르게 매가 두들겨 맞았다**는 뜻입니다. 
        평균으로 돌아가려는 '회귀 본능' 때문에 1~3일 내에 기술적 반등이 나올 확률이 매우 높습니다.
    * **전술적 판단:** 볼린저 하단 터치와 이격도 과매도가 동시에 발생하면, 그것은 **'단기 바닥'**일 확률이 90% 이상인 아주 강력한 매수 신호입니다.

    ---

    ### 💡 캡틴을 위한 단기 매매 공식
    1.  **거시 지표(4번 화면)**가 초록색(`RISK ON`)인지 확인한다.
    2.  이 화면에서 **두 지표가 동시에 🟢 BUY**를 외치는지 확인한다.
    3.  확신이 선다면 **방아쇠를 당긴다(매수).**
    """)