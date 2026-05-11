import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Macro Indicators", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty:
    st.error("⚠️ 데이터가 없습니다. 메인 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("🌐 Macro Indicators (거시 경제 레이더)")
st.caption("경기 침체를 6~12개월 선행하는 거시 지표들을 추적합니다.")

latest      = df.iloc[-1]
latest_date = latest['Date'].strftime('%Y-%m-%d')

# ── 신호 계산 ──────────────────────────────────────────────────────────

# 1. 수익률 곡선 (Yield Curve)
yield_ok     = 'Yield_Curve' in df.columns
yield_val    = latest.get('Yield_Curve', None)
yield_inv    = bool(yield_val < 0) if yield_val is not None and pd.notna(yield_val) else False
# 역전 지속 일수
if yield_ok:
    inv_streak = int((df['Yield_Curve'] < 0).iloc[::-1].cumprod().sum())
else:
    inv_streak = 0

# 2. 기준금리 (Fed Funds Rate)
rate_ok      = 'Fed_Rate' in df.columns
rate_val     = latest.get('Fed_Rate', None)
rate_rising  = False
if rate_ok and pd.notna(rate_val):
    rate_3m_ago = df['Fed_Rate'].iloc[-63] if len(df) > 63 else df['Fed_Rate'].iloc[0]
    rate_rising = float(rate_val) > float(rate_3m_ago)

# 3. 실업률 (Unemployment)
unemp_ok     = 'Unemployment' in df.columns
unemp_val    = latest.get('Unemployment', None)
unemp_alert  = bool(float(unemp_val) > 4.5) if unemp_ok and pd.notna(unemp_val) else False

# 4. 유가 (WTI)
oil_ok       = 'Oil_WTI' in df.columns
oil_val      = latest.get('Oil_WTI', None)
oil_spike    = False
if oil_ok and pd.notna(oil_val):
    oil_3m_ago = df['Oil_WTI'].iloc[-63] if len(df) > 63 else df['Oil_WTI'].iloc[0]
    if pd.notna(oil_3m_ago) and float(oil_3m_ago) > 0:
        oil_chg    = (float(oil_val) - float(oil_3m_ago)) / float(oil_3m_ago) * 100
        oil_spike  = oil_chg > 30  # 3개월 내 30% 이상 급등 = 스태그플레이션 경고

# ── 경기 침체 위험 스코어 ──────────────────────────────────────────────
recession_flags = []
if yield_inv:    recession_flags.append("수익률 곡선 역전")
if rate_rising:  recession_flags.append("기준금리 인상 중")
if unemp_alert:  recession_flags.append("실업률 위험 수위")
if oil_spike:    recession_flags.append("유가 급등 (스태그플레이션)")

rec_score = len(recession_flags)

# ── 요약 배너 ──────────────────────────────────────────────────────────
st.subheader(f"📊 거시 경제 레이더 (기준일: {latest_date})")

if rec_score >= 3:
    st.error(f"🚨 **[경기침체 고위험]** 위험 신호 {rec_score}개 감지: {', '.join(recession_flags)}")
elif rec_score == 2:
    st.warning(f"⚠️ **[경기침체 주의]** 위험 신호 {rec_score}개: {', '.join(recession_flags)}")
elif rec_score == 1:
    st.info(f"🟡 **[경기 경계]** 위험 신호 1개: {recession_flags[0]}")
else:
    st.success("🟢 **[거시 환경 안정]** 경기침체 선행 신호 없음")

st.divider()

# ── 지표 카드 ──────────────────────────────────────────────────────────
cards = st.columns(4)

def metric_card(col, title, value_str, badge, badge_color, desc):
    col.markdown(
        f"<div style='border:1px solid #444;border-radius:8px;padding:14px;height:140px;'>"
        f"<p style='margin:0;color:#aaa;font-size:0.85em;'>{title}</p>"
        f"<h2 style='margin:4px 0;color:white;'>{value_str}</h2>"
        f"<p style='margin:0 0 4px;font-size:0.85em;color:{badge_color};font-weight:bold;'>{badge}</p>"
        f"<p style='margin:0;color:#888;font-size:0.75em;'>{desc}</p>"
        f"</div>",
        unsafe_allow_html=True
    )

with cards[0]:
    if yield_ok and pd.notna(yield_val):
        v_str  = f"{float(yield_val):+.2f}%"
        badge  = f"⚠️ 역전 {inv_streak}일째" if yield_inv else "✅ 정상"
        bcolor = "#FF4B4B" if yield_inv else "#00FF00"
        desc   = "음수 = 경기침체 6~12개월 선행"
    else:
        v_str, badge, bcolor, desc = "N/A", "데이터 없음", "#888", "DB 업데이트 필요"
    metric_card(cards[0], "📉 수익률 곡선 (10Y-2Y)", v_str, badge, bcolor, desc)

with cards[1]:
    if rate_ok and pd.notna(rate_val):
        v_str  = f"{float(rate_val):.2f}%"
        badge  = "📈 인상 중 (긴축)" if rate_rising else "📉 인하 또는 동결"
        bcolor = "#FFC107" if rate_rising else "#00FF00"
        desc   = "인상 = 유동성 축소, 주식 역풍"
    else:
        v_str, badge, bcolor, desc = "N/A", "데이터 없음", "#888", "DB 업데이트 필요"
    metric_card(cards[1], "🏦 연방기금금리 (Fed Rate)", v_str, badge, bcolor, desc)

with cards[2]:
    if unemp_ok and pd.notna(unemp_val):
        v_str  = f"{float(unemp_val):.1f}%"
        badge  = "🚨 위험 (4.5% 초과)" if unemp_alert else "✅ 정상 범위"
        bcolor = "#FF4B4B" if unemp_alert else "#00FF00"
        desc   = "4.5% 초과 = 경기침체 동행 신호"
    else:
        v_str, badge, bcolor, desc = "N/A", "데이터 없음", "#888", "DB 업데이트 필요"
    metric_card(cards[2], "👷 실업률 (Unemployment)", v_str, badge, bcolor, desc)

with cards[3]:
    if oil_ok and pd.notna(oil_val):
        v_str  = f"${float(oil_val):.1f}"
        badge  = "🔥 급등 (스태그플레이션 경고)" if oil_spike else "✅ 안정"
        bcolor = "#FF4B4B" if oil_spike else "#00FF00"
        desc   = "3개월 30%↑ = 소비·기업 비용 압박"
    else:
        v_str, badge, bcolor, desc = "N/A", "데이터 없음", "#888", "DB 업데이트 필요"
    metric_card(cards[3], "🛢️ WTI 원유 가격", v_str, badge, bcolor, desc)

st.divider()

# ── 차트 ──────────────────────────────────────────────────────────────
available_rows = []
subplot_titles_list = []
row_heights_list    = []

if yield_ok:
    available_rows.append('yield')
    subplot_titles_list.append("📉 수익률 곡선 (10Y-2Y) — 0 아래 = 역전 = 침체 경고")
    row_heights_list.append(0.28)
if rate_ok:
    available_rows.append('rate')
    subplot_titles_list.append("🏦 연방기금금리 (Fed Rate)")
    row_heights_list.append(0.24)
if unemp_ok:
    available_rows.append('unemp')
    subplot_titles_list.append("👷 실업률 (Unemployment Rate)")
    row_heights_list.append(0.24)
if oil_ok:
    available_rows.append('oil')
    subplot_titles_list.append("🛢️ WTI 원유 가격")
    row_heights_list.append(0.24)

if not available_rows:
    st.warning("거시 지표 데이터가 없습니다. DB를 업데이트하세요.")
    st.stop()

n_rows = len(available_rows)
# 높이 정규화
total_h = sum(row_heights_list)
row_heights_list = [h / total_h for h in row_heights_list]

fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                    vertical_spacing=0.06,
                    row_heights=row_heights_list,
                    subplot_titles=subplot_titles_list)

plot_df = df.tail(252 * 4)  # 4년치
row_idx = 1

if 'yield' in available_rows:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Yield_Curve'],
                             name="10Y-2Y", line=dict(color='gold', width=2)), row=row_idx, col=1)
    fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="red",
                  annotation_text="역전선 (0%)", annotation_position="top left",
                  row=row_idx, col=1)
    # 역전 구간 음영
    inv_mask = plot_df['Yield_Curve'] < 0
    if inv_mask.any():
        fig.add_trace(go.Scatter(x=plot_df.loc[inv_mask, 'Date'],
                                 y=plot_df.loc[inv_mask, 'Yield_Curve'],
                                 fill='tozeroy', fillcolor='rgba(255,0,0,0.15)',
                                 line=dict(width=0), name="역전 구간", showlegend=True),
                      row=row_idx, col=1)
    row_idx += 1

if 'rate' in available_rows:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Fed_Rate'],
                             name="Fed Rate", line=dict(color='tomato', width=2)), row=row_idx, col=1)
    row_idx += 1

if 'unemp' in available_rows:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Unemployment'],
                             name="Unemployment", line=dict(color='lightcoral', width=2)), row=row_idx, col=1)
    fig.add_hline(y=4.5, line_width=1.5, line_dash="dash", line_color="orange",
                  annotation_text="위험선 (4.5%)", annotation_position="top left",
                  row=row_idx, col=1)
    row_idx += 1

if 'oil' in available_rows:
    fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Oil_WTI'],
                             name="WTI Oil", line=dict(color='peru', width=2)), row=row_idx, col=1)
    row_idx += 1

fig.update_layout(height=max(800, 220 * n_rows), template="plotly_dark",
                  hovermode="x unified", showlegend=True,
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
for ann in fig['layout']['annotations']:
    ann['font'] = dict(size=14, color='white')

st.plotly_chart(fig, use_container_width=True)

with st.expander("🤖 AI 거시경제 가이드: 각 지표의 의미와 투자 전략", expanded=True):
    st.markdown("""
    ### 📉 수익률 곡선 역전 (10Y - 2Y Yield Spread)
    > **역사적으로 가장 정확한 경기침체 예측 지표 (88% 적중률)**

    * **정상 (양수):** 10년 금리 > 2년 금리 = 경제 성장 기대. 주식 투자에 우호적.
    * **역전 (음수):** 단기 금리가 장기 금리보다 높음 = 투자자들이 미래 경기를 비관. **역전 후 평균 12개월 내 침체**.
    * **전략:** 역전이 시작되면 주식 비중을 서서히 줄이고, 역전이 해소되며 급등할 때 다시 진입을 고려.

    ### 🏦 연방기금금리 (Fed Funds Rate)
    * **인상 사이클:** 유동성 축소 → 기업 차입 비용 증가 → 주가 하방 압력
    * **인하 사이클:** 유동성 공급 → 주식 밸류에이션 확대 → 주가 상승 촉매
    * **전략:** 금리 인하 전환점 = 역사적으로 최고의 주식 매수 타이밍

    ### 👷 실업률 (Unemployment Rate)
    * **4.5% 미만:** 고용 시장 건강 = 소비 유지 = 기업 실적 지지
    * **4.5% 초과:** 경기 침체 동행 신호. 실업률은 후행 지표이므로 이미 악화됐다면 침체 한가운데.
    * **Sahm Rule:** 실업률 3개월 평균이 최근 12개월 최저치보다 0.5%p 이상 오르면 침체 신호

    ### 🛢️ WTI 원유 가격
    * **완만한 상승:** 경제 성장 신호 (수요 증가)
    * **급등 (3개월 30%+):** 스태그플레이션 경고 — 물가 상승 + 성장 둔화 = 최악의 환경
    * **급락:** 수요 붕괴 신호 (경기침체 동반 가능)
    """)
