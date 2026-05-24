import streamlit as st
import google.generativeai as genai
import sys

st.set_page_config(page_title="제미나이 진단 모드", page_icon="🔧")

st.title("🔧 제미나이 환경 및 모델 진단")

# 1. 설치된 버전 확인
st.subheader("1. 서버 환경 정보")
st.write(f"- 파이썬 버전: `{sys.version}`")
st.write(f"- 구글 AI 라이브러리 버전: `{genai.__version__}`")

# 2. 사용 가능한 모델 리스트 확인
st.subheader("2. 내 API 키로 사용 가능한 모델 목록")
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    
    # generateContent(글쓰기)가 가능한 모델만 추려냅니다.
    valid_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            valid_models.append(m.name)
            
    if valid_models:
        for name in valid_models:
            st.success(f"✅ 사용 가능: `{name}`")
    else:
        st.warning("사용 가능한 글쓰기 모델이 없습니다. API 키를 확인하세요.")
        
except KeyError:
    st.error("Secrets에 GEMINI_API_KEY가 없습니다.")
except Exception as e:
    st.error(f"❌ 에러 발생: {e}")
