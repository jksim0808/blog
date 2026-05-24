import streamlit as st
from generator import get_blog_content
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import pyperclip
import streamlit as st
import time
import traceback # 상세 에러 추적을 위한 모듈 추가
import google.generativeai as genai

# Streamlit의 secrets에서 키를 가져오는 방식으로 변경

try:
    # 기존 코드
    # api_key = st.secrets["GEMINI_API_KEY"] 
    
    # 수정된 코드 (끝에 .strip() 을 붙여주세요)
    api_key = st.secrets["GEMINI_API_KEY"].strip() 
    
    genai.configure(api_key=api_key)
except KeyError:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()


# 현재 파일이 있는 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.title("네이버 블로그 자동 발행기")
topic = st.text_input("주제를 입력하세요")

if st.button("글 생성 및 발행"):
    # 시작 시간 기록
    start_time = time.time() 
    
    try:
        # 1단계: Gemini 글 생성
        with st.spinner("1/2단계: Gemini API로 글 생성 중... (보통 10~20초 소요)"):
            content = get_blog_content(topic) # (합치기 하셨다면 해당 함수 호출)
            
            # 중간 점검: 글 생성에 걸린 시간
            gen_time = time.time() - start_time
            st.success(f"글 생성 완료! (소요 시간: {gen_time:.1f}초)")
            
            # 생성된 제목 살짝 보여주기
            st.info(f"생성된 제목: {content.get('title', '제목 없음')}")

        # 2단계: 셀레니움 발행
        with st.spinner("2/2단계: 네이버 블로그에 자동 발행 중... (브라우저 작업)"):
            step2_start = time.time()
            post_to_naver(content) # (합치기 하셨다면 해당 함수 호출)
            
            post_time = time.time() - step2_start
            st.success(f"블로그 발행 완전 성공! (발행 소요 시간: {post_time:.1f}초)")
            
    except Exception as e:
        # 에러가 발생하면 spinner가 멈추고 아래 붉은 박스가 뜹니다.
        st.error(f"작업 중 오류가 발생했습니다: {e}")
        
        # 개발자용 상세 에러 로그를 화면에 바로 출력 (디버깅용)
        with st.expander("상세 에러 로그 보기"):
            st.code(traceback.format_exc())



