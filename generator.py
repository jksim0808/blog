import google.generativeai as genai
import json

def get_blog_content(topic):
    genai.configure(api_key="발급받은키")
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"'{topic}'에 대해 블로그 글을 써줘. JSON 형식으로 {{'title': '...', 'body': '...', 'tags': '...'}} 구조로 응답해줘."
    
    response = model.generate_content(prompt)
    return json.loads(response.text)
