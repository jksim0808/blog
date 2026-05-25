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
import re

# 이전 테스트에서 남은 사진들 삭제 (깨끗한 테스트를 위해)
for file in ["step1_written.png", "step2_panel.png", "step3_done.png", "error_screen.png"]:
    if os.path.exists(file):
        os.remove(file)

# ---------------------------------------------------------
# 1. Gemini API 글 생성 함수 (HTML 프롬프트 적용 및 들여쓰기 수정 완료)
# ---------------------------------------------------------
def get_blog_content(topic):
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    '{topic}'에 대한 정보성 네이버 블로그 포스팅을 작성해줘.
    반드시 아래의 JSON 형식으로만 대답해. 다른 말은 절대 하지마.
    {{
        "title": "블로그 글 제목 (HTML 없이 순수 텍스트)",
        "body": "블로그 본문 내용 (단락 구분은 <p></p>로, 빈 줄은 <p><br></p>로, 중요한 단어는 <b>강조</b>하는 등 네이버 블로그에 적합한 완벽한 HTML 태그 형태로 작성해줘)",
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
    
    # 봇 탐지 우회(Stealth) 옵션
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

        # 1. 쿠키 심기
        driver.get("https://www.naver.com")
        time.sleep(2)
        driver.add_cookie({"name": "NID_AUT", "value": nid_aut, "domain": ".naver.com"})
        driver.add_cookie({"name": "NID_SES", "value": nid_ses, "domain": ".naver.com"})
        driver.refresh()
        time.sleep(2)

        # 2. 내 블로그 전용 우회 주소로 이동
        driver.get("https://blog.naver.com/MyBlog.naver")
        time.sleep(3)
        my_actual_blog_url = driver.current_url 
        if my_actual_blog_url.endswith("/"):
            my_actual_blog_url = my_actual_blog_url[:-1]

        # 3. 글쓰기 전용 주소 직행
        write_url = f"{my_actual_blog_url}/postwrite"
        try:
            driver.get(write_url)
        except UnexpectedAlertPresentException:
            pass

        time.sleep(5)

        # 4. 팝업 닫기
        try:
            alert = driver.switch_to.alert
            alert.accept()
            time.sleep(1)
        except NoAlertPresentException:
            pass

        # 5. iframe 전환
        try:
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it("mainFrame"))
            time.sleep(1)
        except:
            pass 

        # 도움말 팝업 제거
        try:
            driver.execute_script("document.querySelectorAll('[class*=\"help\"], [class*=\"guide\"], [class*=\"popup\"], [class*=\"layer\"], [class*=\"dimmed\"]').forEach(el => el.style.display = 'none');")
            time.sleep(1)
        except:
            pass

# 6. 제목 입력 (JS 주입 + 스페이스바 트리거)
        title_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "se-title-text"))
        )
        
        # JS로 텍스트를 한 번에 꽂아 넣습니다.
        driver.execute_script("""
            var titleWrapper = document.querySelector('.se-title-text');
            var titleEl = titleWrapper.querySelector('[contenteditable="true"]') || titleWrapper;
            titleEl.focus();
            titleEl.innerHTML = '<span>' + arguments[0] + '</span>';
        """, data['title'])
        time.sleep(0.5)
        
        # 💡 [핵심 치트키] 텍스트 주입 후, 키보드로 '스페이스바'를 누르고 '백스페이스'로 지웁니다!
        # 네이버(React)가 이 키보드 신호를 받고 주입된 텍스트를 즉시 저장(Save)합니다.
        ActionChains(driver).send_keys(Keys.SPACE).send_keys(Keys.BACKSPACE).perform()
        time.sleep(1)

        # 7. 본문 입력 (JS 주입 + 안전장치 + 스페이스바 트리거)
        content_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "se-content"))
        )
        
        # 만약 제미나이가 <p> 태그 없이 그냥 글씨만 줬을 경우를 대비한 '줄바꿈/굵은글씨 방어 코드'
        body_html = data['body']
        if "<p>" not in body_html:
            import re
            formatted_parts = []
            for line in body_html.split('\n'):
                line = line.strip()
                if not line:
                    formatted_parts.append('<p><br></p>')
                else:
                    line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                    formatted_parts.append('<p><span>' + line + '</span></p>')
            body_html = "".join(formatted_parts)
            
        # 완성된 HTML을 본문에 꽂아 넣습니다.
        driver.execute_script("""
            var bodyWrapper = document.querySelector('.se-main-container') || document.querySelector('.se-content');
            var bodyEl = bodyWrapper.querySelector('[contenteditable="true"]') || bodyWrapper;
            bodyEl.focus();
            bodyEl.innerHTML = arguments[0];
        """, body_html)
        time.sleep(0.5)
        
        # 💡 본문도 마찬가지로 스페이스바 -> 백스페이스로 렌더링 갱신을 터뜨립니다!
        ActionChains(driver).send_keys(Keys.SPACE).send_keys(Keys.BACKSPACE).perform()
        time.sleep(1)
        
        # 📸 [CCTV 1] 본문 작성 완료 사진
        driver.save_screenshot("step1_written.png")

        # 8. 첫 번째 '발행' 버튼 클릭 (우측 상단)
        clicked_first = False
        publish_btns = driver.find_elements(By.XPATH, "//button[contains(., '발행')]")
        for btn in publish_btns:
            if btn.is_displayed() and btn.text.strip() == "발행":
                # 복구된 버튼을 가장 확실하게 누르는 JS 강제 클릭 사용
                driver.execute_script("arguments[0].click();", btn)
                clicked_first = True
                break
                
        if not clicked_first:
            raise Exception("우측 상단 '발행' 버튼을 화면에서 찾을 수 없습니다.")
            
        time.sleep(3) # 우측 설정 패널이 열릴 때까지 대기

        driver.save_screenshot("step2_panel.png")
        # 9. 최종 '발행' 버튼 클릭 (우측 패널 하단)
        clicked_final = False
        final_btns = driver.find_elements(By.XPATH, "//button[contains(., '발행')]")
        for btn in reversed(final_btns):
            if btn.is_displayed() and btn.text.strip() == "발행":
                driver.execute_script("arguments[0].click();", btn)
                clicked_final = True
                break
                
        if not clicked_final:
            raise Exception("최종 '발행' 버튼을 찾을 수 없습니다.")
            
        time.sleep(5) 
        
        # 📸 [CCTV 3] 최종 발행 처리 직후 사진
        driver.save_screenshot("step3_done.png")
        time.sleep(2) # 서버 통신 마무리 대기
        
    except Exception as e:
        driver.save_screenshot("error_screen.png")
         # 에러의 정확한 이름(타입)을 같이 출력하도록 수정
        error_name = type(e).__name__
        st.error(f"❌ 작업 중 오류가 발생했습니다: [{error_name}] {e}")
        raise e
       
    finally:
        driver.quit()

# ---------------------------------------------------------
# 3. Streamlit 웹 UI
# ---------------------------------------------------------
st.set_page_config(page_title="블로그 자동 포스팅", page_icon="📝")

st.title("📝 네이버 블로그 자동 포스팅 봇")

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

        # 작업 완료 후 과정 사진 보여주기
        st.write("### 📸 봇이 작업한 화면 로그 (CCTV)")
        cols = st.columns(3)
        if os.path.exists("step1_written.png"):
            cols[0].image("step1_written.png", caption="1. 글 작성 완료")
        if os.path.exists("step2_panel.png"):
            cols[1].image("step2_panel.png", caption="2. 발행 패널 오픈")
        if os.path.exists("step3_done.png"):
            cols[2].image("step3_done.png", caption="3. 최종 전송 화면")

    except Exception as e:
        st.error(f"❌ 작업 중 오류가 발생했습니다: {e}")
        
        if os.path.exists("error_screen.png"):
            st.image("error_screen.png", caption="막혀버린 네이버 브라우저 화면 📸")
            
        with st.expander("상세 에러 로그 보기 (디버깅용)"):
            st.code(traceback.format_exc())
