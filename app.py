import streamlit as st
import pandas as pd
import os
import importlib

st.set_page_config(page_title="Captain's Strategic Command", layout="wide")

# 데이터 로드 (공통)
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv('liquidity_db.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values('Date')

df = load_data()

# 사이드바 메뉴 구성
def get_screens():
    files = [f[:-3] for f in os.listdir('collectors') if f.endswith('.py') and f != '__init__.py']
    return [f.capitalize() for f in files]

selected = st.sidebar.radio("📡 전술 화면 선택", ["Home"] + get_screens())

if selected == "Home":
    st.title("🚀 Captain's Strategic Hub")
    st.write("분석할 전술 화면을 선택하십시오.")
else:
    # 선택한 모듈을 동적으로 불러와서 render_screen 함수 실행
    module_name = f"collectors.{selected.lower()}"
    module = importlib.import_module(module_name)
    
    # 핵심: 각 파일에 정의된 render_screen 함수 호출!
    if hasattr(module, "render_screen"):
        module.render_screen(df)
    else:
        st.error(f"{selected}.py 파일에 render_screen 함수가 정의되지 않았습니다.")
