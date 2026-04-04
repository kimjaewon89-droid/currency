from datetime import datetime, timedelta
import pandas as pd
# 분리된 수집기 불러오기 (폴더 구조에 따라 import 경로 조절)
from collectors.liquidity import get_liquidity_data

def run_strategy_update():
    print("🚀 [전술 업데이트] 데이터 수집 시작...")
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=3650)
    
    # 데이터 수집 호출
    data = get_liquidity_data(start_date, end_date)
    
    # 1. 데이터가 None인지 먼저 확인 (방어적 코드)
    if data is None:
        print("⚠️ 에러: 수집 엔진으로부터 None이 반환되었습니다.")
        return

    # 2. 이제 안전하게 .empty 확인
    if not data.empty and 'Total_Assets' in data.columns:
        # Net_Liquidity 계산
        data['Net_Liquidity'] = data['Total_Assets'] - (data.get('TGA', 0) + data.get('Reverse_Repo', 0))
        
        data.index.name = 'Date'
        data = data.reset_index()
        data.to_csv('liquidity_db.csv', index=False)
        print(f"✅ 전술 데이터베이스 업데이트 완료! ({len(data)}행)")
    else:
        print("⚠️ 업데이트 실패: 데이터가 비어있거나 필수 지표(Total_Assets)가 누락되었습니다.")

if __name__ == "__main__":
    run_strategy_update()
