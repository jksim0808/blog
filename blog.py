import streamlit as st
from generator import get_blog_content
from blog_bot import post_to_naver
import sys
import os

# 현재 파일이 있는 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from blog_bot import post_to_naver

st.title("네이버 블로그 자동 발행기")
topic = st.text_input("주제를 입력하세요")

if st.button("글 생성 및 발행"):
    with st.spinner("글 생성 중..."):
        content = get_blog_content(topic)
        st.write("제목:", content['title'])
    
    with st.spinner("블로그 발행 중..."):
        post_to_naver(content)
        st.success("발행 완료!")
