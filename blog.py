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

        # 💡 5. 상단 메뉴바 완전히 삭제 (가림 현상 방지)
        driver.execute_script("""
            var blockers = document.querySelectorAll('header, [class*="header"], [class*="toolbar"], [class*="floating"], [class*="menu"]');
            for (var i = 0; i < blockers.length; i++) {
                blockers[i].style.display = 'none';
            }
            window.scrollTo(0, 0);
        """)
        time.sleep(1)

        # 💡 6. 제목 입력 (클릭 따로, 텍스트 주입 따로! 완벽 분리)
        title_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "se-title-text")))
        ActionChains(driver).move_to_element(title_box).click().perform()
        time.sleep(1) # 커서가 깜빡일 때까지 확실히 기다립니다.
        
        # 시스템 레벨에서 텍스트를 강제로 복사-붙여넣기 합니다.
        driver.execute_cdp_cmd("Input.insertText", {"text": data['title']})
        time.sleep(1)

        # 💡 7. 본문 입력
        content_box = driver.find_element(By.CLASS_NAME, "se-content")
        ActionChains(driver).move_to_element(content_box).click().perform()
        time.sleep(1) # 커서 활성화 대기
        
        for line in data['body'].split('\n'):
            if line.strip():
                driver.execute_cdp_cmd("Input.insertText", {"text": line})
            # 엔터키만 ActionChains로 칩니다.
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            time.sleep(0.05)
            
        time.sleep(1)
        driver.save_screenshot("step1_written.png")

        # 💡 8. 상단 메뉴바 복구 (발행 버튼 부활)
        driver.execute_script("""
            var blockers = document.querySelectorAll('header, [class*="header"], [class*="toolbar"], [class*="floating"], [class*="menu"]');
            for (var i = 0; i < blockers.length; i++) {
                blockers[i].style.display = '';
            }
        """)
        time.sleep(2)

        # 9. 첫 번째 '발행' 버튼 클릭
        publish_btns = driver.find_elements(By.XPATH, "//button[contains(., '발행')]")
        clicked_first = False
        for btn in publish_btns:
            if btn.is_displayed() and btn.text.strip() == "발행":
                driver.execute_script("arguments[0].click();", btn)
                clicked_first = True
                break
                
        if not clicked_first:
            raise Exception("우측 상단 '발행' 버튼을 찾을 수 없습니다.")
            
        time.sleep(3) 
        driver.save_screenshot("step2_panel.png")

        # 10. 카테고리 선택
        try:
            category_btn = driver.find_element(By.CSS_SELECTOR, ".se-category-button, .btn_select")
            driver.execute_script("arguments[0].click();", category_btn)
            time.sleep(1)
            
            first_cat = driver.find_element(By.CSS_SELECTOR, ".list_category li, .se-category-list li")
            driver.execute_script("arguments[0].click();", first_cat)
            time.sleep(1)
        except Exception as e:
            pass

        # 11. 최종 '발행' 버튼 클릭
        final_btns = driver.find_elements(By.XPATH, "//button[contains(., '발행')]")
        clicked_final = False
        for btn in reversed(final_btns):
            if btn.is_displayed() and btn.text.strip() == "발행":
                driver.execute_script("arguments[0].click();", btn)
                clicked_final = True
                break
                
        if not clicked_final:
            raise Exception("최종 '발행' 버튼을 찾을 수 없습니다.")
            
        time.sleep(7) 
        
        try:
            alert = driver.switch_to.alert
            alert.accept()
        except NoAlertPresentException:
            pass

        driver.save_screenshot("step3_done.png")
        time.sleep(2) 
        
    except Exception as e:
        driver.save_screenshot("error_screen.png")
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
