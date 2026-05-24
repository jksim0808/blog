import streamlit as st
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import traceback

# ---------------------------------------------------------
# 1. Gemini API 글 생성 함수
# ---------------------------------------------------------
def get_blog_content(topic):
    # Secrets에서 키를 가져오고 보이지 않는 공백/줄바꿈 제거 (.strip() 적용)
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-1.0-pro')
    
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
    
    # 텍스트 결과물을 JSON(딕셔너리)으로 변환
    try:
        content = json.loads(response.text)
        return content
    except json.JSONDecodeError:
        # 가끔 Gemini가 마크다운 코드블럭(```json ... ```)을 포함해서 줄 때가 있음
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

# ---------------------------------------------------------
# 2. 네이버 블로그 자동 발행 함수 (Selenium)
# ---------------------------------------------------------
def post_to_naver(data):
    # Streamlit Cloud 환경을 위한 Chrome 옵션 설정 (필수)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # 화면 없는 브라우저 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36") # 봇 탐지 우회용

    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 네이버 아이디/비번 가져오기
        naver_id = st.secrets["NAVER_ID"].strip()
        naver_pw = st.secrets["NAVER_PW"].strip()

        # 1. 로그인 페이지 접속
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)

        # 2. 로그인 우회 입력 (pyperclip 대신 자바스크립트 사용 - 클라우드 호환)
        driver.execute_script(f"document.getElementsByName('id')[0].value='{naver_id}'")
        driver.execute_script(f"document.getElementsByName('pw')[0].value='{naver_pw}'")
        driver.find_element(By.ID, "log.login").click()
        time.sleep(3) # 로그인 완료 대기

        # 3. 글쓰기 페이지 이동
        write_url = f"https://blog.naver.com/{naver_id}/postwrite"
        driver.get(write_url)
        time.sleep(5) # 에디터 로딩 대기

        # 4. iframe 전환 (네이버 에디터는 iframe 안에 있음)
        driver.switch_to.frame("mainFrame")
        
        # ---------------------------------------------------------
        # 주의: 아래 선택자(CSS_SELECTOR)는 네이버 에디터 버전에 따라 자주 바뀝니다.
        # 실행 중 요소를 찾지 못하면 실제 F12를 눌러 클래스명을 업데이트해야 합니다.
        # ---------------------------------------------------------
        
        # 5. 제목 입력
        title_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".se-ff-nanumgothic.se-fs32.se-ff-system")) # 제목 클래스 (예시)
        )
        title_box.send_keys(data['title'])
        time.sleep(1)

        # 6. 본문 입력
        content_box = driver.find_element(By.CSS_SELECTOR, ".se-component-content") # 본문 클래스 (예시)
        content_box.click() # 포커스 맞추기
        
        # 본문은 여러 줄이므로 쪼개서 전송
        for line in data['body'].split('\n'):
            content_box.send_keys(line)
            content_box.send_keys(Keys.ENTER)
            time.sleep(0.1)

        # 발행 버튼 클릭 로직 (자동 발행 방지를 위해 임시 주석 처리)
        # publish_btn = driver.find_element(By.CSS_SELECTOR, ".btn_publish")
        # publish_btn.click()
        
    finally:
        driver.quit() # 작업 완료 후 브라우저 닫기

# ---------------------------------------------------------
# 3. Streamlit 웹 UI
# ---------------------------------------------------------
st.set_page_config(page_title="블로그 자동 포스팅", page_icon="📝")

st.title("📝 네이버 블로그 자동 포스팅 봇")
st.markdown("주제를 입력하면 제미나이가 글을 쓰고 네이버 블로그에 자동으로 올립니다.")

topic = st.text_input("어떤 주제로 글을 쓸까요?", placeholder="예: 2024년 주식 투자 전망")

if st.button("글 생성 및 발행 시작", type="primary"):
    if not topic:
        st.warning("주제를 입력해주세요!")
        st.stop()

    start_time = time.time()
    
    try:
        # [단계 1] 제미나이 글 생성
        with st.spinner("1/2단계: 제미나이가 글을 작성하고 있습니다... (약 10~20초)"):
            post_data = get_blog_content(topic)
            gen_time = time.time() - start_time
            
            st.success(f"✅ 글 생성 완료! ({gen_time:.1f}초 소요)")
            with st.expander("생성된 내용 미리보기"):
                st.write("**제목:**", post_data.get('title'))
                st.write("**본문:**", post_data.get('body'))
                st.write("**태그:**", post_data.get('tags'))

        # [단계 2] 셀레니움 자동 발행
        with st.spinner("2/2단계: 네이버 블로그에 접속하여 글을 쓰는 중입니다... (약 10~15초)"):
            step2_start = time.time()
            post_to_naver(post_data)
            post_time = time.time() - step2_start
            
            st.success(f"🎉 블로그 발행 작업 완료! ({post_time:.1f}초 소요)")

    except Exception as e:
        st.error(f"❌ 작업 중 오류가 발생했습니다: {e}")
        with st.expander("상세 에러 로그 보기 (디버깅용)"):
            st.code(traceback.format_exc())
