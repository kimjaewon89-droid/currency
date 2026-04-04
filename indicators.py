import pandas as pd

def calculate_indicators(df):
    """Raw 데이터를 받아 실질 유동성 등을 계산합니다."""
    if df.empty:
        return df
    
    # Net Liquidity 계산 (이미 main.py에서 계산해서 저장했다면 생략 가능하지만 안전하게 유지)
    if 'Total_Assets' in df.columns:
        df['Net_Liquidity'] = df['Total_Assets'] - (df.get('TGA', 0) + df.get('Reverse_Repo', 0))
    
    return df

def apply_shift(df, column, days):
    """특정 컬럼에 시차를 적용합니다."""
    if column in df.columns:
        return df[column].shift(days)
    return pd.Series([None] * len(df))
