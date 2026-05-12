import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

st.set_page_config(page_title="KR Smart Money", layout="wide")

KR_DB_PATH = "kr_smart_money_db.csv"


@st.cache_data(ttl=3600)
def load_kr_data():
    if not os.path.exists(KR_DB_PATH):
        return pd.DataFrame()
    df = pd.read_csv(KR_DB_PATH)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


df = load_kr_data()

st.title("🇰🇷 KR Smart Money — 외국인/기관 수급")

# ── 데이터 없을 때 ─────────────────────────────────────────────────────────
if df.empty or "kospi_foreign_total" not in df.columns:
    st.info("📋 수급 데이터가 없습니다.")
    st.markdown("""
    KRX 수급 데이터는 **로컬 PC에서 수집** 후 사용할 수 있습니다.

    **수집 방법 (로컬 터미널):**
    ```
    pip install pykrx
    py -c "from collectors.kr_smart_money import update_kr_smart_money_db; update_kr_smart_money_db()"
    ```
    수집 완료 후 생성된 `kr_smart_money_db.csv`를 GitHub에 push하면 이 페이지에 표시됩니다.
    """)
    st.stop()

# ── 신호 계산 ──────────────────────────────────────────────────────────────
try:
    from utils.kor_signals import compute_kor_supply_signals
    sig = compute_kor_supply_signals(df)
except Exception as e:
    st.error(f"신호 계산 오류: {e}")
    st.stop()

latest      = df.iloc[-1]
latest_date = latest["Date"].strftime("%Y-%m-%d")

score      = sig["supply_score"]
verdict    = sig["verdict"]
has_danger = sig["has_danger"]
fi_1d      = sig["fi_1d"]
inst_1d    = sig["inst_1d"]
fi_5d      = sig["fi_5d_sum"]
inst_5d    = sig["inst_5d_sum"]
fi_z       = sig["fi_5d_zscore"]
inst_z     = sig["inst_5d_zscore"]

bar_color = "#00FF00" if score >= 3 else "#FFC107" if score == 2 else "#FF4B4B"
bar_pct   = int(score / 4 * 100)
v_emoji   = "✅" if verdict == "BUY" else "🚫"

# ── 점수 배너 ──────────────────────────────────────────────────────────────
st.caption(f"기준일: {latest_date}")
st.markdown(
    f"<div style='background:rgba(255,255,255,0.04);border:1px solid #555;"
    f"border-radius:8px;padding:12px 20px;margin-bottom:18px;'>"
    f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
    f"<div><b style='color:#ddd;'>🎯 수급 신호 점수</b>"
    f"<h1 style='margin:4px 0;color:{bar_color};'>{score} / 4</h1>"
    f"<p style='margin:0;color:#aaa;font-size:0.9em;'>{v_emoji} {verdict}</p></div>"
    f"<div style='text-align:right;'>"
    f"<p style='margin:0 0 4px;color:#aaa;font-size:0.85em;'>외국인 5일 누적</p>"
    f"<h2 style='margin:0;color:{bar_color};'>{fi_5d:+,.0f}억</h2></div></div>"
    f"<div style='background:#333;border-radius:4px;height:8px;margin-top:12px;'>"
    f"<div style='background:{bar_color};width:{bar_pct}%;height:8px;border-radius:4px;'></div></div>"
    f"</div>",
    unsafe_allow_html=True,
)

if sig["danger_fi_dump"]:
    st.error("🚨 외국인 대량 순매도 (5일 -3000억 이하) — 진입 자제")
if sig["danger_dual_sell"]:
    st.error("🚨 외국인+기관 동반 대량 매도 — 수급 공백")

st.divider()

# ── 당일 지표 카드 ─────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("외국인 당일 (KOSPI)", f"{fi_1d:+,.0f}억",   delta=f"5일 {fi_5d:+,.0f}억")
c2.metric("기관 당일 (KOSPI)",   f"{inst_1d:+,.0f}억", delta=f"5일 {inst_5d:+,.0f}억")
c3.metric("외국인 5일 Z-score",  f"{fi_z:+.2f}",       delta="평균 초과" if fi_z > 0 else "평균 미달")
c4.metric("기관 5일 Z-score",    f"{inst_z:+.2f}",     delta="평균 초과" if inst_z > 0 else "평균 미달")

# ── 신호 카드 4종 ──────────────────────────────────────────────────────────
st.markdown("##### 📊 수급 신호")

def _card(title, desc, is_on):
    color = "#00FF00" if is_on else "#FF4B4B"
    label = "ON 🟢" if is_on else "OFF 🔴"
    return (
        f"<div style='border:1px solid #444;border-radius:8px;padding:14px;"
        f"background:rgba(255,255,255,0.02);margin-bottom:10px;'>"
        f"<p style='margin:0 0 6px;color:#ddd;font-size:0.9em;'><b>{title}</b></p>"
        f"<h3 style='margin:0;color:{color};'>{label}</h3>"
        f"<p style='margin:4px 0 0;color:#aaa;font-size:0.82em;'>{desc}</p></div>"
    )

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(_card("외국인 단기 유입",  f"5일 {fi_5d:+,.0f}억 / z={fi_z:+.2f}",   sig["fi_flow_on"]),   unsafe_allow_html=True)
with s2:
    st.markdown(_card("외국인 추세 전환",  "20일 합계 방향 상향 전환",                 sig["fi_trend_on"]),  unsafe_allow_html=True)
with s3:
    st.markdown(_card("기관 단기 유입",    f"5일 {inst_5d:+,.0f}억 / z={inst_z:+.2f}", sig["inst_flow_on"]), unsafe_allow_html=True)
with s4:
    st.markdown(_card("외국인+기관 동반", "당일 동시 순매수",                           sig["dual_buy_on"]),  unsafe_allow_html=True)

st.divider()

# ── 기간 슬라이더 ──────────────────────────────────────────────────────────
max_dt = df["Date"].max().to_pydatetime()
min_dt = df["Date"].min().to_pydatetime()
date_range = st.slider("📅 기간", min_dt, max_dt,
                        (max_dt - timedelta(days=180), max_dt), format="YYYY-MM-DD")
mask = (df["Date"] >= date_range[0]) & (df["Date"] <= date_range[1])
dv   = df[mask].copy()

fi_col   = "kospi_foreign_total"
inst_col = "kospi_institutional_total"
dv["fi_bn"]   = dv[fi_col].astype(float)   / 1e8 if fi_col   in dv.columns else 0
dv["inst_bn"] = dv[inst_col].astype(float) / 1e8 if inst_col in dv.columns else 0

# ── 차트: 일별 순매수 Bar + KOSPI200 오버레이 ──────────────────────────────
has_k200 = "k200_close" in dv.columns
has_5d   = "kospi_foreign_net_5d" in dv.columns

fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
    row_heights=[0.6, 0.4],
    specs=[[{"secondary_y": has_k200}], [{"secondary_y": False}]],
    subplot_titles=("일별 순매수 (억원)" + (" + KOSPI200" if has_k200 else ""),
                    "5일 누적 순매수 추이 (억원)"),
)

fi_colors   = ["#4C9BE8" if v >= 0 else "#FF4B4B" for v in dv["fi_bn"]]
inst_colors = ["#50C878" if v >= 0 else "#FF6B6B" for v in dv["inst_bn"]]

fig.add_trace(go.Bar(x=dv["Date"], y=dv["fi_bn"],   name="외국인",
                     marker_color=fi_colors,   opacity=0.85), row=1, col=1)
fig.add_trace(go.Bar(x=dv["Date"], y=dv["inst_bn"], name="기관",
                     marker_color=inst_colors, opacity=0.70), row=1, col=1)

if has_k200:
    fig.add_trace(go.Scatter(x=dv["Date"], y=dv["k200_close"],
                             name="KOSPI200", line=dict(color="darkorange", width=2)),
                  row=1, col=1, secondary_y=True)

if has_5d:
    dv["fi_5d_bn"]   = dv["kospi_foreign_net_5d"].astype(float) / 1e8
    fig.add_trace(go.Scatter(x=dv["Date"], y=dv["fi_5d_bn"],
                             name="외국인 5일 누적", fill="tozeroy",
                             line=dict(color="#4C9BE8", width=2)), row=2, col=1)
if "kospi_inst_net_5d" in dv.columns:
    dv["inst_5d_bn"] = dv["kospi_inst_net_5d"].astype(float) / 1e8
    fig.add_trace(go.Scatter(x=dv["Date"], y=dv["inst_5d_bn"],
                             name="기관 5일 누적", fill="tozeroy",
                             line=dict(color="#50C878", width=2)), row=2, col=1)

fig.add_hline(y=0, line_dash="dot", line_color="#888", row=2, col=1)
fig.update_layout(height=750, template="plotly_dark", hovermode="x unified",
                  barmode="overlay",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
for ann in fig["layout"]["annotations"]:
    ann["font"] = dict(size=13, color="white")

st.plotly_chart(fig, use_container_width=True)

# ── 어드민 ────────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
with st.expander("⚙️ 데이터 수집 (관리자)", expanded=False):
    pwd = st.text_input("암호:", type="password", key="kr_pwd")
    if pwd == "cap":
        st.success("인증 완료")
        if st.button("📡 한국 수급 DB 업데이트", type="primary"):
            with st.spinner("KRX 수집 중... (1~2분)"):
                try:
                    from collectors.kr_smart_money import update_kr_smart_money_db
                    ok = update_kr_smart_money_db(save_path=KR_DB_PATH, years=2)
                    if ok:
                        st.cache_data.clear()
                        st.success("완료!")
                        st.rerun()
                    else:
                        st.error("실패")
                except Exception as e:
                    st.error(f"{e}")
    elif pwd:
        st.error("암호 불일치")

with st.expander("📖 수급 신호 읽는 법", expanded=False):
    st.markdown("""
    ### 외국인/기관 수급 신호 4종

    | 신호 | 조건 | 의미 |
    |------|------|------|
    | 외국인 단기 유입 | 5일 누적 +500억↑ + z-score > 0 | 외국인이 평균 이상 집중 매수 |
    | 외국인 추세 전환 | 20일 합계가 5거래일 전보다 증가 | 유입 방향 전환점 감지 |
    | 기관 단기 유입 | 5일 누적 +300억↑ + z-score > 0 | 연기금·투신 집중 매수 |
    | 동반 매수 | 외국인+기관 당일 동시 순매수 | 가장 신뢰도 높은 진입 신호 |

    **수급 점수 2점 이상 + 위험 없음 → BUY**

    ### 위험 플래그
    - 🚨 **외국인 대량 매도**: 5일 합계 -3000억 이하
    - 🚨 **동반 대량 매도**: 외국인 당일 -500억 + 기관 -300억 동시
    """)
