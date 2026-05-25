import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import traceback
import os

# 이전 테스트 사진 삭제
for file in ["step1_written.png", "step2_panel.png", "step3_done.png", "error_screen.png"]:
    if os.path.exists(file):
        os.remove(file)

# ---------------------------------------------------------
# 1. Gemini API 글 생성 함수
# ---------------------------------------------------------
def get_blog_content(topic):
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    '{topic}'에 대한 정보성 네이버 블로그 포스팅을 작성해줘.
    반드시 아래의 JSON 형식으로만 대답해. 다른 말은 절대 하지마.
    {{
        "title": "블로그 글 제목",
        "body": "블로그 본문 내용 (HTML 태그 없이 줄바꿈은 \\n 으로 처리)",
        "tags": "#태그1 #태그2 #태그3"
    }}
    """
    
    response = model.generate_content(prompt)
    
    try:
        content = json.loads(response.text)
        return content
    except json.JSONDecodeError:
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

# ---------------------------------------------------------
# 2. 네이버 블로그 자동 발행 함수 (Selenium)
# ---------------------------------------------------------
def post_to_naver(data):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    chrome_options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        nid_aut = st.secrets["NAVER_NID_AUT"].strip()
        nid_ses = st.secrets["NAVER_NID_SES"].strip()

        # 1. 로그인
        driver.get("https://www.naver.com")
        time.sleep(2)
        driver.add_cookie({"name": "NID_AUT", "value": nid_aut, "domain": ".naver.com"})
        driver.add_cookie({"name": "NID_SES", "value": nid_ses, "domain": ".naver.com"})
        driver.refresh()
        time.sleep(2)

        # 2. 내 블로그 이동
        driver.get("https://blog.naver.com/MyBlog.naver")
        time.sleep(3)
        my_actual_blog_url = driver.current_url 
        if my_actual_blog_url.endswith("/"):
            my_actual_blog_url = my_actual_blog_url[:-1]

        # 3. 글쓰기 페이지 진입
        write_url = f"{my_actual_blog_url}/postwrite"
        try:
            driver.get(write_url)
        except UnexpectedAlertPresentException:
            pass

        time.sleep(5)

        # 4. 방해 팝업 닫기
        try:
            alert = driver.switch_to.alert
            alert.accept()
            time.sleep(1)
        except NoAlertPresentException:
            pass

        try:
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it("mainFrame"))
            time.sleep(1)
        except:
            pass 

        try:
            driver.execute_script("document.querySelectorAll('[class*=\"help\"], [class*=\"guide\"], [class*=\"popup\"], [class*=\"layer\"], [class*=\"dimmed\"]').forEach(el => el.style.display = 'none');")
            time.sleep(1)
        except:
            pass

        # 💡 5. 상단 메뉴바 "완전 삭제" (이전 성공했던 display: none 방식으로 롤백)
        driver.execute_script("""
            var blockers = document.querySelectorAll('header, [class*="header"], [class*="toolbar"], [class*="floating"], [class*="menu"]');
            for (var i = 0; i < blockers.length; i++) {
                blockers[i].style.display = 'none';
            }
            window.scrollTo(0, 0);
        """)
        time.sleep(1)

        # 6. 제목 입력 (유리창이 사라졌으니 정상적으로 클릭됨!)
        title_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "se-title-text")))
        ActionChains(driver).move_to_element(title_box).click().pause(1).send_keys(data['title']).perform()
        time.sleep(1)

        # 7. 본문 입력
        content_box = driver.find_element(By.CLASS_NAME, "se-content")
        ActionChains(driver).move_to_element(content_box).click().pause(1).
