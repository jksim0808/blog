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
    
    # 최신 제미나이 2.5 플래시 모델 적용
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
    
    # 봇 탐지 우회(Stealth) 옵션
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Streamlit 클라우드 크롬 경로 설정
    chrome_options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Secrets에서 쿠키(입장권) 가져오기
        nid_aut = st.secrets["NAVER_NID_AUT"].strip()
        nid_ses = st.secrets["NAVER_NID_SES"].strip()

        # 1. 네이버 메인 접속 후 쿠키 심기
        driver.get("https://www.naver.com")
        time.sleep(2)
        driver.add_cookie({"name": "NID_AUT", "value": nid_aut, "domain": ".naver.com"})
        driver.add_cookie({"name": "NID_SES", "value": nid_ses, "domain": ".naver.com"})
        driver.refresh()
        time.sleep(2)

        # 2. 내 블로그 전용 우회 주소로 이동하여 진짜 주소 알아내기
        driver.get("https://blog.naver.com/MyBlog.naver")
        time.sleep(3)
        my_actual_blog_url = driver.current_url 
        if my_actual_blog_url.endswith("/"):
            my_actual_blog_url = my_actual_blog_url[:-1]

        # 3. 글쓰기 전용 주소로 직행
        write_url = f"{my_actual_blog_url}/postwrite"
        try:
            driver.get(write_url)
        except UnexpectedAlertPresentException:
            pass # 이동 순간 뜨는 팝업 무시

        time.sleep(5) # 에디터 로딩 대기

        # 4. 임시저장 등 불쑥 튀어나오는 팝업 확실하게 닫기
        try:
            alert = driver.switch_to.alert
            alert.accept()
            time.sleep(1)
        except NoAlertPresentException:
            pass

# 5. iframe 전환 (글쓰기 에디터 창 진입)
        try:
            driver.switch_to.frame("mainFrame")
        except UnexpectedAlertPresentException:
            alert = driver.switch_to.alert
            alert.accept()
            time.sleep(1)
            driver.switch_to.frame("mainFrame")
        
        time.sleep(3) # 에디터 내부가 다 그려질 때까지 넉넉히 대기

        # 🚨 [도움말 팝업 완벽 철거] 자바스크립트로 화면을 가리는 요소들을 통째로 지워버립니다.
        try:
            nuke_popup_js = """
            // '도움말', '팝업', '가이드'와 관련된 모든 창을 찾아서 숨겨버림
            var overlays = document.querySelectorAll('div[class*="help"], div[class*="guide"], div[class*="popup"], div[class*="layer"]');
            overlays.forEach(function(el) { el.style.display = 'none'; });
            
            // 닫기(X) 버튼이 보이면 모조리 눌러버림
            var closeBtns = document.querySelectorAll('button[class*="close"], button[class*="Close"], a[class*="close"]');
            closeBtns.forEach(function(btn) { btn.click(); });
            """
            driver.execute_script(nuke_popup_js)
            time.sleep(1)
        except:
            pass

        # 6. 제목 입력
        title_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-ff-nanumgothic.se-fs32.se-ff-system"))
        )
        # 마우스로 클릭하는 대신, 오버레이를 무시하는 'JS 강제 클릭' 사용
        driver.execute_script("arguments[0].click();", title_box) 
        time.sleep(0.5)
        title_box.send_keys(data['title'])
        time.sleep(1)

        # 7. 본문 입력
        content_box = driver.find_element(By.CSS_SELECTOR, ".se-component-content")
        driver.execute_script("arguments[0].click();", content_box) # 본문도 강제 클릭
        time.sleep(0.5)
        
        for line in data['body'].split('\n'):
            content_box.send_keys(line)
            content_box.send_keys(Keys.ENTER)
            time.sleep(0.1)

        # 🚨 발행 버튼 클릭 로직 (테스트가 완전히 성공하면 아래 두 줄의 주석(#)을 지우세요!)
        # publish_btn = driver.find_element(By.CSS_SELECTOR, ".btn_publish")
        # publish_btn.click()
        # time.sleep(3)
            
    except Exception as e:
        # 에러 발생 시 막힌 화면 캡처
        driver.save_screenshot("error_screen.png")
        raise e
        
    finally:
        driver.quit()

# ---------------------------------------------------------
# 3. Streamlit 웹 UI
# ---------------------------------------------------------
st.set_page_config(page_title="블로그 자동 포스팅", page_icon="📝")

st.title("📝 네이버 블로그 자동 포스팅 봇")
st.markdown("주제를 입력하면 제미나이가 글을 쓰고 네이버 블로그에 자동으로 올립니다.")

topic = st.text_input("어떤 주제로 글을 쓸까요?", placeholder="예: 이동식 동물미용차 장점")

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
        
        # 에러 스크린샷 띄우기
        if os.path.exists("error_screen.png"):
            st.image("error_screen.png", caption="막혀버린 네이버 브라우저 화면 📸")
            
        with st.expander("상세 에러 로그 보기 (디버깅용)"):
            st.code(traceback.format_exc())
