import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

# --- [UI 로직: app.py에서 호출할 함수] ---
def render_screen(df):
    st.title("🛡️ Liquidity Tactical View")
    
    # 1. 컨트롤러 (본문 상단)
    col1, col2 = st.columns([2, 1])
    with col1:
        start_def = df['Date'].max().to_pydatetime() - timedelta(days=365)
        end_def = df['Date'].max().to_pydatetime()
        selected_range = st.slider("기간 설정", 
                                   df['Date'].min().to_pydatetime(), 
                                   df['Date'].max().to_pydatetime(),
                                   (start_def, end_def), format="YYYY-MM-DD")
    with col2:
        shift = st.number_input("유동성 시차(일)", 0, 90, 21)

    # 2. 데이터 처리
    mask = (df['Date'] >= selected_range[0]) & (df['Date'] <= selected_range[1])
    # 시차 적용은 원본 보존을 위해 복사본에 수행
    df_plot = df.copy()
    df_plot['Shifted'] = df_plot['Net_Liquidity'].shift(shift)
    df_plot = df_plot.loc[mask]

    # 3. 그래프 생성
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])
    
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Net_Liquidity'], 
                             name="Raw", line=dict(color='yellow', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['Shifted'], 
                             name="Shifted", line=dict(color='mediumpurple', width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['SP500'], 
                             name="S&P500", line=dict(color='darkorange')), row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=df_plot['VIX'], 
                             name="VIX", fill='tozeroy', line=dict(color='crimson')), row=2, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    st.plotly_chart(fig, use_container_width=True)

def get_liquidity_data(start_date, end_date):
    fred = Fred(api_key=os.environ.get('FRED_API_KEY'))
    # M2SL 추가
    fred_tickers = {
        'Total_Assets': 'WALCL', 
        'TGA': 'WDTGAL', 
        'Reverse_Repo': 'RRPONTSYD',
        'M2': 'M2SL'  # <--- 신규 추가
    }
    
    fred_dfs = []
    for name, ticker in fred_tickers.items():
        s = fred.get_series(ticker, observation_start=start_date, observation_end=end_date)
        df = pd.DataFrame(s, columns=[name])
        # M2 단위 보정 (Billions -> Millions)
        if name == 'M2':
            df[name] = df[name] * 1000
        df.index = pd.to_datetime(df.index).normalize()
        fred_dfs.append(df)
    
    combined = pd.concat(fred_dfs, axis=1).join(mkt_df, how='outer').ffill().bfill()
    return combined
