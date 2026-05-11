import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="Signal Backtest", layout="wide")


@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('liquidity_db.csv'):
        return pd.DataFrame()
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date').reset_index(drop=True)


df = load_data()

if df.empty or 'SP500' not in df.columns:
    st.error("⚠️ 데이터가 없습니다. 메인 화면에서 DB를 업데이트 해주세요.")
    st.stop()

st.title("📊 Signal Backtest (신호 역사적 검증)")
st.caption("각 신호가 발생했을 때 실제로 얼마나 수익이 났는지 과거 데이터로 검증합니다.")

# ── 지표 전처리 ────────────────────────────────────────────────────────
df = df.copy()

# 이동평균
df['SMA_50']  = df['SP500'].rolling(50).mean()
df['SMA_200'] = df['SP500'].rolling(200).mean()

# RSI
delta = df['SP500'].diff()
gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
loss  = -1 * delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
df['RSI'] = 100 - (100 / (1 + gain / loss))

# MACD
df['MACD']        = df['SP500'].ewm(span=12, adjust=False).mean() - df['SP500'].ewm(span=26, adjust=False).mean()
df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

# Bollinger Band
df['BB_Mid']   = df['SP500'].rolling(20).mean()
df['BB_Lower'] = df['BB_Mid'] - df['SP500'].rolling(20).std() * 2

# Stochastic RSI
rsi_min  = df['RSI'].rolling(14).min()
rsi_max  = df['RSI'].rolling(14).max()
stoch_k  = (df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9) * 100
df['StochRSI_K'] = stoch_k.rolling(3).mean()

# Smart Money 비율 (SPY/TLT)
if 'SPY' in df.columns and 'TLT' in df.columns:
    ratio = df['SPY'] / df['TLT']
    df['SPY_TLT_50MA']  = ratio.rolling(50).mean()
    df['SPY_TLT_200MA'] = ratio.rolling(200).mean()

# ── 신호 생성 함수 ─────────────────────────────────────────────────────

def signal_ma_golden_cross(df):
    """50MA가 200MA를 상향 돌파하는 날"""
    cross = (df['SMA_50'] > df['SMA_200']) & (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))
    return cross.astype(int)


def signal_rsi_oversold(df):
    """RSI가 30 아래에서 30을 상향 돌파하는 날"""
    cross = (df['RSI'] > 30) & (df['RSI'].shift(1) <= 30)
    return cross.astype(int)


def signal_macd_cross(df):
    """MACD가 0 이하에서 시그널 상향 돌파"""
    cross = ((df['MACD'] < 0) &
             (df['MACD'] > df['MACD_Signal']) &
             (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1)))
    return cross.astype(int)


def signal_bollinger_touch(df):
    """가격이 볼린저 하단 터치"""
    return (df['SP500'] <= df['BB_Lower']).astype(int)


def signal_stoch_rsi(df):
    """Stochastic RSI K선이 20 아래에서 상향 돌파"""
    cross = (df['StochRSI_K'] > 20) & (df['StochRSI_K'].shift(1) <= 20)
    return cross.astype(int)


def signal_vix_capitulation(df):
    """VIX가 30 찍고 하락 전환 (최근 5일 내 30 이상 & 오늘 하락)"""
    if 'VIX' not in df.columns:
        return pd.Series(0, index=df.index)
    vix_panic = df['VIX'].rolling(5).max() >= 30
    vix_drop  = df['VIX'] < df['VIX'].shift(1)
    return (vix_panic & vix_drop).astype(int)


def signal_spy_tlt_cross(df):
    """SPY/TLT 비율이 50MA > 200MA 상향 돌파"""
    if 'SPY_TLT_50MA' not in df.columns:
        return pd.Series(0, index=df.index)
    cross = ((df['SPY_TLT_50MA'] > df['SPY_TLT_200MA']) &
             (df['SPY_TLT_50MA'].shift(1) <= df['SPY_TLT_200MA'].shift(1)))
    return cross.astype(int)


SIGNAL_REGISTRY = {
    "📈 MA 골든크로스 (50/200)":      signal_ma_golden_cross,
    "📉 RSI 30 상향 돌파":             signal_rsi_oversold,
    "🔄 MACD 0선 아래 상향 교차":      signal_macd_cross,
    "📊 볼린저 하단 터치":             signal_bollinger_touch,
    "⚡ Stochastic RSI 반등":          signal_stoch_rsi,
    "😨 VIX 항복 (Capitulation)":      signal_vix_capitulation,
    "🦅 SPY/TLT 골든크로스":           signal_spy_tlt_cross,
}

# ── 백테스트 엔진 ──────────────────────────────────────────────────────

def run_backtest(df, signal_series, forward_days=20):
    """
    신호 발생일 기준 forward_days 이후 수익률 계산.
    Returns: dict with stats
    """
    df = df.copy()
    df['Signal']  = signal_series.values
    df['Fwd_Ret'] = df['SP500'].pct_change(forward_days).shift(-forward_days) * 100

    signal_rows = df[df['Signal'] == 1].dropna(subset=['Fwd_Ret'])

    if len(signal_rows) < 3:
        return None

    returns = signal_rows['Fwd_Ret'].values
    wins    = returns[returns > 0]
    losses  = returns[returns <= 0]

    hit_rate    = len(wins) / len(returns) * 100
    avg_win     = float(wins.mean())   if len(wins)   > 0 else 0.0
    avg_loss    = float(losses.mean()) if len(losses) > 0 else 0.0
    avg_return  = float(returns.mean())
    payoff      = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Sharpe (연환산)
    std = returns.std()
    sharpe = (avg_return / std * np.sqrt(252 / forward_days)) if std > 0 else 0.0

    return {
        "신호 횟수":    len(returns),
        "승률 (%)":    round(hit_rate, 1),
        "평균 수익 (%)": round(avg_return, 2),
        "평균 상승 (%)": round(avg_win, 2),
        "평균 손실 (%)": round(avg_loss, 2),
        "손익비 (P/L)": round(payoff, 2),
        "Sharpe":       round(sharpe, 2),
        "_returns":     returns,
        "_dates":       signal_rows['Date'].values,
    }


# ── UI ─────────────────────────────────────────────────────────────────
col_ctrl1, col_ctrl2 = st.columns([1, 2])
with col_ctrl1:
    forward_days = st.selectbox("📅 수익률 측정 기간", [5, 10, 20, 60], index=2,
                                help="신호 발생 후 몇 영업일 뒤 수익률을 측정할지 선택")
with col_ctrl2:
    selected_signals = st.multiselect("🎯 검증할 신호 선택", list(SIGNAL_REGISTRY.keys()),
                                       default=list(SIGNAL_REGISTRY.keys()))

st.divider()

if not selected_signals:
    st.info("검증할 신호를 선택해 주세요.")
    st.stop()

# ── 백테스트 실행 ──────────────────────────────────────────────────────
results_list = []
all_results  = {}

for sig_name in selected_signals:
    try:
        sig_series = SIGNAL_REGISTRY[sig_name](df)
        result     = run_backtest(df, sig_series, forward_days)
        if result:
            all_results[sig_name] = result
            row = {k: v for k, v in result.items() if not k.startswith('_')}
            row['신호'] = sig_name
            results_list.append(row)
    except Exception as e:
        st.warning(f"{sig_name} 계산 실패: {e}")

# ── 요약 테이블 ────────────────────────────────────────────────────────
if results_list:
    summary_df = pd.DataFrame(results_list).set_index('신호')
    display_cols = ["신호 횟수", "승률 (%)", "평균 수익 (%)", "평균 상승 (%)", "평균 손실 (%)", "손익비 (P/L)", "Sharpe"]
    summary_df = summary_df[display_cols]

    st.markdown(f"### 📋 신호별 {forward_days}일 수익률 요약")

    def color_cell(val, col):
        if col == "승률 (%)":
            if val >= 65: return "color: #00FF00"
            if val >= 50: return "color: #FFC107"
            return "color: #FF4B4B"
        if col == "평균 수익 (%)":
            if val > 2:   return "color: #00FF00"
            if val > 0:   return "color: #FFC107"
            return "color: #FF4B4B"
        if col == "Sharpe":
            if val > 1:   return "color: #00FF00"
            if val > 0:   return "color: #FFC107"
            return "color: #FF4B4B"
        return ""

    styled = summary_df.style
    for col in ["승률 (%)", "평균 수익 (%)", "Sharpe"]:
        styled = styled.applymap(lambda v: color_cell(v, col), subset=[col])

    st.dataframe(styled, use_container_width=True)

    # ── 베스트 신호 배지 ──────────────────────────────────────────────
    if len(results_list) > 1:
        best_winrate = max(results_list, key=lambda x: x["승률 (%)"])
        best_return  = max(results_list, key=lambda x: x["평균 수익 (%)"])
        best_sharpe  = max(results_list, key=lambda x: x["Sharpe"])

        b1, b2, b3 = st.columns(3)
        b1.metric("🏆 최고 승률", best_winrate["신호"].split(" ", 1)[1][:20],
                  f"{best_winrate['승률 (%)']:.1f}%")
        b2.metric("💰 최고 평균 수익", best_return["신호"].split(" ", 1)[1][:20],
                  f"+{best_return['평균 수익 (%)']:.2f}%")
        b3.metric("📐 최고 Sharpe", best_sharpe["신호"].split(" ", 1)[1][:20],
                  f"{best_sharpe['Sharpe']:.2f}")

    st.divider()

    # ── 신호별 수익률 분포 차트 ────────────────────────────────────────
    st.markdown("### 📈 신호별 수익률 분포")

    n = len(all_results)
    if n > 0:
        cols_per_row = min(n, 3)
        rows_needed  = (n + cols_per_row - 1) // cols_per_row

        items = list(all_results.items())
        for row_i in range(rows_needed):
            row_items = items[row_i * cols_per_row: (row_i + 1) * cols_per_row]
            chart_cols = st.columns(len(row_items))

            for ci, (sig_name, res) in enumerate(row_items):
                returns = res['_returns']
                hit     = res['승률 (%)']
                avg_r   = res['평균 수익 (%)']

                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=returns,
                    nbinsx=20,
                    marker_color=['#00FF00' if r > 0 else '#FF4B4B' for r in returns],
                    name="수익률 분포"
                ))
                fig.add_vline(x=0, line_width=2, line_dash="dash", line_color="white")
                fig.add_vline(x=avg_r, line_width=2, line_color="yellow",
                              annotation_text=f"평균 {avg_r:+.1f}%", annotation_position="top right")
                fig.update_layout(
                    title=dict(text=f"{sig_name[:30]}<br><sup>승률 {hit:.0f}% | 평균 {avg_r:+.2f}%</sup>",
                               font_size=13),
                    height=280, template="plotly_dark",
                    margin=dict(l=20, r=20, t=60, b=20),
                    showlegend=False,
                    xaxis_title=f"{forward_days}일 수익률 (%)",
                    yaxis_title="빈도"
                )
                chart_cols[ci].plotly_chart(fig, use_container_width=True)

    # ── 최고 신호 시계열 ──────────────────────────────────────────────
    if len(all_results) >= 1:
        best_key = max(all_results, key=lambda k: all_results[k]['승률 (%)'])
        best_res = all_results[best_key]
        best_dates = best_res['_dates']

        st.markdown(f"### 📅 {best_key} — 신호 발생 시점 (S&P 500)")

        plot_df = df.tail(252 * 3)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SP500'],
                                  name="S&P 500", line=dict(color='white', width=1.5)))

        # 신호 발생 마커
        sig_df = df[df['Date'].isin(best_dates)]
        fig2.add_trace(go.Scatter(
            x=sig_df['Date'], y=sig_df['SP500'],
            mode='markers', marker=dict(color='lime', size=10, symbol='triangle-up'),
            name=f"신호 ({len(sig_df)}회)"
        ))
        fig2.update_layout(height=380, template="plotly_dark", hovermode="x unified",
                           legend=dict(orientation="h"))
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("데이터가 부족하여 백테스트를 실행할 수 없습니다. DB를 업데이트 후 다시 시도하세요.")

with st.expander("📖 백테스트 지표 해석 가이드", expanded=False):
    st.markdown(f"""
    **{forward_days}일 기준으로 신호 발생 후 실제 수익률을 측정합니다.**

    | 지표 | 의미 | 우수 기준 |
    |------|------|-----------|
    | **승률 (%)** | 신호 발생 후 플러스 수익 비율 | ≥ 65% |
    | **평균 수익 (%)** | 신호별 평균 수익률 | > 0% |
    | **손익비 (P/L)** | 평균 수익 / 평균 손실 비율 | ≥ 1.5 |
    | **Sharpe** | 위험 대비 수익 (연환산) | ≥ 1.0 |

    > ⚠️ **주의:** 과거 수익률은 미래를 보장하지 않습니다. 백테스트는 신호의 '경향성'을 파악하는 도구입니다.
    > 여러 신호가 동시에 발생하면 수익률이 크게 향상되는 경향이 있으며, 이를 메인 페이지의 **통합 점수**로 확인하세요.
    """)
