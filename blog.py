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

# 이전 테스트에서 남은 사진들 삭제 (깨끗한 테스트를 위해)
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

# 6. 제목 입력 (가림막 철거 후 정석 타이핑)
        title_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "se-title-text"))
        )
        
        # 💡 핵심 1: 마우스 클릭을 방해하는 네이버의 상단 툴바, 메뉴바를 싹 다 찾아내서 화면에서 지워버립니다.
        driver.execute_script("""
            var blockers = document.querySelectorAll('header, [class*="header"], [class*="toolbar"], [class*="floating"], [class*="menu"]');
            for (var i = 0; i < blockers.length; i++) {
                blockers[i].style.display = 'none';
            }
            window.scrollTo(0, 0);
        """)
        time.sleep(1)
        
        # 💡 핵심 2: 방해물이 없어졌으니, 당당하게 진짜 마우스로 제목 칸을 클릭하고 즉시 타자를 칩니다!
        ActionChains(driver).move_to_element(title_box).click().send_keys(data['title']).perform()
        time.sleep(1)

        # 7. 본문 입력
        content_box = driver.find_element(By.CLASS_NAME, "se-content")
        
        # 본문 칸 마우스 클릭 (커서 활성화)
        ActionChains(driver).move_to_element(content_box).click().perform()
        time.sleep(0.5)
        
        # 한 줄씩 엔터키를 치며 사람과 100% 똑같은 방식으로 입력합니다.
        for line in data['body'].split('\n'):
            ActionChains(driver).send_keys(line).send_keys(Keys.ENTER).perform()
            time.sleep(0.05)
            
        time.sleep(1)
        # 📸 [CCTV 1] 본문 작성 완료 사진 (이번엔 반드시 글씨가 꽉 차 있습니다!)
        driver.save_screenshot("step1_written.png")
       # 💡 [추가] 아까 숨겨뒀던 상단 메뉴바(발행 버튼 포함)를 다시 화면에 나타나게 복구합니다!
        driver.execute_script("""
            var blockers = document.querySelectorAll('header, [class*="header"], [class*="toolbar"], [class*="floating"], [class*="menu"]');
            for (var i = 0; i < blockers.length; i++) {
                blockers[i].style.display = '';
            }
        """)
        time.sleep(1)

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
