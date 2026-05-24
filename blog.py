import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service # 크롬 서비스 추가
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import traceback
import os # 스크린샷 저장을 위한 모듈 추가

# ---------------------------------------------------------
# 1. Gemini API 글 생성 함수
# ---------------------------------------------------------
def get_blog_content(topic):
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    
    # 최신 모델 적용 완료
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
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 클라우드 크롬 경로 설정
    chrome_options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        naver_id = st.secrets["NAVER_ID"].strip()
        naver_pw = st.secrets["NAVER_PW"].strip()

        # 로그인 페이지 접속
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)

        # 로그인 우회 입력
        driver.execute_script(f"document.getElementsByName('id')[0].value='{naver_id}'")
        driver.execute_script(f"document.getElementsByName('pw')[0].value='{naver_pw}'")
        driver.find_element(By.ID, "log.login").click()
        time.sleep(3)

        # 글쓰기 페이지 이동
        write_url = f"https://blog.naver.com/{naver_id}/postwrite"
        driver.get(write_url)
        time.sleep(5)

        # iframe 전환 (mainFrame을 찾는 부분)
        driver.switch_to.frame("mainFrame")
        
        # 제목 입력
        title_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-ff-nanumgothic.se-fs32.se-ff-system"))
        )
        title_box.send_keys(data['title'])
        time.sleep(1)

        # 본문 입력
        content_box = driver.find_element(By.CSS_SELECTOR, ".se-component-content")
        content_box.click()
        
        for line in data['body'].split('\n'):
            content_box.send_keys(line)
            content_box.send_keys(Keys.ENTER)
            time.sleep(0.1)
            
    except Exception as e:
        # 에러 발생 시 브라우저 화면 캡처
        driver.save_screenshot("error_screen.png")
        raise e  # 발생한 에러를 밖으로 던짐
        
    finally:
        driver.quit()

# ---------------------------------------------------------
# 3. Streamlit 웹 UI
# ---------------------------------------------------------
st.set_page_config(page_title="블로그 자동 포스팅", page_icon="📝")

st.title("📝 네이버 블로그 자동 포스팅 봇")
st.markdown("주제를 입력하면 제미나이가 글을 쓰고 네이버 블로그에 자동으로 올립니다.")

topic = st.text_input("어떤 주제로 글을 쓸까요?", placeholder="예: 2026년 인공지능 트렌드")

if st.button("글 생성 및 발행 시작", type="primary"):
    if not topic:
        st.warning("주제를 입력해주세요!")
        st.stop()

    start_time = time.time()
    
    try:
        with st.spinner("1/2단계: 제미나이가 글을 작성하고 있습니다..."):
            post_data = get_blog_content(topic)
            gen_time = time.time() - start_time
            
            st.success(f"✅ 글 생성 완료! ({gen_time:.1f}초 소요)")

        with st.spinner("2/2단계: 네이버 블로그에 접속하여 글을 쓰는 중입니다..."):
            step2_start = time.time()
            post_to_naver(post_data)
            post_time = time.time() - step2_start
            
            st.success(f"🎉 블로그 발행 작업 완료! ({post_time:.1f}초 소요)")

    except Exception as e:
        st.error(f"❌ 작업 중 오류가 발생했습니다: {e}")
        
        # 에러 스크린샷 파일이 존재하면 화면에 띄움
        if os.path.exists("error_screen.png"):
            st.image("error_screen.png", caption="막혀버린 네이버 브라우저 화면 📸")
            
        with st.expander("상세 에러 로그 보기 (디버깅용)"):
            st.code(traceback.format_exc())
