from datetime import datetime, timedelta
import pandas as pd
# 분리된 수집기 불러오기 (폴더 구조에 따라 import 경로 조절)
from collectors.liquidity import get_liquidity_data

def run_strategy_update():
    print("🚀 [전술 업데이트] 데이터 수집 시작...")
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=3650) # 10년치
    
    # 1. 유동성 데이터 수집
    data = get_liquidity_data(start_date, end_date)
    
    # 2. 지표 계산 (Net Liquidity)
    if not data.empty and 'Total_Assets' in data.columns:
        data['Net_Liquidity'] = data['Total_Assets'] - (data.get('TGA', 0) + data.get('Reverse_Repo', 0))
        
        # 인덱스 정리 및 저장
        data.index.name = 'Date'
        data = data.reset_index()
        data.to_csv('liquidity_db.csv', index=False)
        print(f"✅ 유동성 데이터 업데이트 완료: {len(data)}행 저장됨.")
    else:
        print("⚠️ 업데이트 실패: 데이터가 비어있습니다.")

if __name__ == "__main__":
    run_strategy_update()
