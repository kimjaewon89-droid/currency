import streamlit as st
from utils.fetcher import update_database

st.set_page_config(page_title="Captain's Hub", layout="wide")

st.title("🚀 Captain's Strategic Hub")
st.write("왼쪽 사이드바에서 분석할 전술 화면을 선택하십시오.")

st.divider()

st.subheader("🔄 전술 데이터베이스 관리")
st.write("아래 버튼을 누르면 연준(FRED) 및 Yahoo Finance에서 최신 데이터를 수집하여 DB를 갱신합니다.")

# Get DB 버튼 로직
if st.button("📡 최신 데이터 수집 (Get DB)", type="primary"):
    with st.spinner("데이터 수집 엔진 가동 중..."):
        try:
            success = update_database()
            if success:
                st.success("✅ 전술 데이터베이스 업데이트 완료! (liquidity_db.csv)")
                st.cache_data.clear() # 기존에 로드된 데이터 캐시 초기화
            else:
                st.error("⚠️ 업데이트 실패: 필수 지표가 누락되었습니다.")
        except Exception as e:
            st.error(f"❌ 데이터 수집 중 에러 발생: {e}")