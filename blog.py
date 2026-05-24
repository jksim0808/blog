import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
import time
import json
import traceback
import os

# ---------------------------------------------------------
# 1. Gemini API 글 생성 함수
# ---------------------------------------------------------
def get_blog_content(topic):
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"'{topic}'에 대한 정보성 네이버 블로그 포스팅을 작성해줘. JSON 형식으로 제목, 본문(줄바꿈\\n), 태그만 작성해."
    response = model.generate_content(prompt)
    
    try:
        content = json.loads(response.text)
        return content
    except:
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

# ---------------------------------------------------------
# 2. 네이버 블로그 자동 발행 함수
# ---------------------------------------------------------
def post_to_naver(data):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        nid_aut = st.secrets["NAVER_NID_AUT"].strip()
        nid_ses = st.secrets["NAVER_NID_SES"].strip()

        # 로그인 입장권 심기
        driver.get("https://www.naver.com")
        driver.add_cookie({"name": "NID_AUT", "value": nid_aut, "domain": ".naver.com"})
        driver.add_cookie({"name": "NID_SES", "value": nid_ses, "domain": ".naver.com"})
        driver.refresh()
        
        # 글쓰기 페이지 이동
        driver.get("https://blog.naver.com/MyBlog.naver")
        time.sleep(3)
        driver.get(f"{driver.current_url}/postwrite")
        time.sleep(5)

        # 에디터 진입
        try:
            WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it("mainFrame"))
        except:
            pass

        # 제목 입력
        title_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "se-title-text")))
        driver.execute_script("arguments[0].click();", title_box)
        ActionChains(driver).send_keys(data['title']).perform()
        
        # 본문 입력
        content_box = driver.find_element(By.CLASS_NAME, "se-content")
        driver.execute_script("arguments[0].click();", content_box)
        for line in data['body'].split('\n'):
            ActionChains(driver).send_keys(line).send_keys(Keys.ENTER).perform()
        
        # 발행 버튼 클릭
        time.sleep(2)
        driver.execute_script("document.querySelectorAll('button, a').forEach(el => { if(el.innerText.includes('발행')) el.click(); });")
        time.sleep(3)
        driver.execute_script("document.querySelectorAll('button').forEach(el => { if(el.innerText.includes('발행')) el.click(); });")
        time.sleep(5)
            
    finally:
        driver.quit()

# ---------------------------------------------------------
# 3. Streamlit 웹 UI (함수들 아래에 위치)
# ---------------------------------------------------------
st.set_page_config(page_title="블로그 자동 포스팅", page_icon="📝")
st.title("📝 네이버 블로그 자동 포스팅 봇")
topic = st.text_input("어떤 주제로 글을 쓸까요?")

if st.button("글 생성 및 발행 시작"):
    with st.spinner("작업 중..."):
        try:
            post_data = get_blog_content(topic)
            post_to_naver(post_data)
            st.success("🎉 성공!")
        except Exception as e:
            st.error(f"오류: {e}")
