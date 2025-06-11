#streamlit run voicebot.py

import streamlit as st 
from audiorecorder import audiorecorder
import openai
import os
from datetime import datetime
from gtts import gTTS 
import base64

## 기능 구현 함수 ##
def STT(audio, apikey):
    filename = "input.mp3"
    audio.export(filename, format = "mp3")
    
    audio_file = open(filename, "rb")
    
    client = openai.OpenAI(api_key = apikey)
    respons = client.audio.transcriptions.create(model="whisper-1", file = audio_file)
    audio_file.close()
    
    os.remove(filename)
    return respons.text

def ask_gpt(prompt, model, apikey):
    client = openai.OpenAI(api_key= apikey)
    response = client.chat.completions.create(
        model = model, 
        messages= prompt)
    gptResponse = response.choices[0].message.content
    return gptResponse

def TTS(response):
    # gTTS를 활용하여 음성 파일 생성
    filename = "output.mp3"
    tts = gTTS(text=response, lang = "ko")
    tts.save(filename)
    
    #음원 파일 자동 재생
    with open(filename, "rb") as f:
        data = f.read()
        b64 = base64.b64decode(data).decode()
        md = f"""
            <audio autoplay="True">
            <source src="data :audio/mp3;base64,{b64}"" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True, )
    # 파일 삭제
    os.remove(filename)
    
## 메인 함수 ##
def main():
    st.set_page_config(
        page_title = "음성 비서 프로그램",
        layout  = "wide")
    
    st.header("🔊 250611_음성 비서 프로그램 실습")
    
    st.markdown("---")

    # 기본 설정
    with st.expander("음성 비서 프로그램?", expanded = True):
        st.write(
        """
        - 음성 비서 프로그램의 UI는 Streamlit을 활용했습니다.
        - STT (Speech-to-text) : OpenAI의 Wisper AI
        - 답변 : OpenAI의 GPT
        - TTS (Text-to-Speech) : 구글의 Google Translate TTS
        """
        )
        
        st.markdown("---")
    # session state 초기화
    if "chat" not in st.session_state :
        st.session_state["chat"]=[]
        
    if "OPENAI_API" not in st.session_state :
        st.session_state["OPENAI_API"]=[]
        
    if "messages" not in st.session_state :
        st.session_state["messages"]=[{"role": "system", "content":"You are  a thoughful assistant. Respond to all input in 25 words and answer in korea"}]
    
    if "check_audio" not in st.session_state :
        st.session_state["check_reset"]=False
        
     # 사이드바 생성
    with st.sidebar:
        st.session_state["OPENAI_API"] = st.text_input(label = "OPENAI API 키", 
                                                       placeholder = "Enter Your API key", 
                                                       value = "",
                                                       type = "password")
        st.markdown("---")
        
        model = st.radio(label = "GPT 모델", options = ["gpt-4", "gpt-4.1-mini"])
        st.markdown("---")
        
        if st.button(label = "초기화"):
            #리셋 코드
            st.session_state["chat"] = []
            st.session_state["messages"] = [{"role": "system", "content":"You are  a thoughful assistant. Respond to all input in 25 words and answer in korea"}]
            st.session_state["check_reset"]= True
    
    
    # 기능 구현 공간
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("질문하기")
        #음성 녹음 아이콘 
        audio = audiorecorder("클릭하여 녹음하기", "녹음 중 ...")
        if (audio.duration_seconds > 0) and (st.session_state["check_reset"]==False) :
        # 녹음 실행시
            # 음성 재생
            st.audio(audio.export().read())
            # 음원 파일에서 텍스트 추출
            question =STT(audio, st.session_state["OPENAI_API"])
            
            # 채팅을 시각화하기 위한 질문 내용 저장
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"]= st.sesstion_state["chat"]+[("user", now, question)]
            # GPT 모델에 넣을 프롬프트를 위해 질문 내용 저장 
            st.session_state["messages"] = st.session_state["messages"]+[{"role": "user", "content": question}]
    
    with col2:
        st.subheader("답변")
        
        if (audio.duration_seconds > 0) and (st.session_state['check_reset']==False) :
            # chatGPT에게 답변 얻기
            response = ask_gpt(st.session_state['messages'], model,
                               st.session_state["OPENAI_API"])
            
            # GPT 모델에 넣을 프롬프트를 위해 답변 내용 저장 
            st.session_state["messages"] = st.session_state["messages"] + [{"role":"system", "content" : response}]
            
            # 채팅 시각화를 위한 답변 내용 저장
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"] + [("bot", now, response)]
            
            # 채팅 형식으로 시각화 하기
            for sender, time, message in st.session_state["chat"] : 
                if sender == "user": # 대화 주체가 사용자 = 질문 파란색 
                    st.write(f"""<div style="display :flex;align-items:center;">
                             <divstyle="background-color: #007AFF; color:white;border-radius:12px; 
                             padding:8px 12px;marginright :8px; ">{message}</div>
                             <div style="font-size :0.8rem;color:gray;">{time}</div></div>""",
                             unsafe_allow_html=True)
                    st.write("")
                else : # 대화 주체가 gpt = 답변 회색 
                    st.write(f"""<div style="display:flex; align-items:center; justifycontent:flex-end;">
                             <div st yle="background-color:lightgray; border-radius:12px; padding :8px 12px;
                             margi n-left :8px;">{message}</di v><di v style="font-size:0 .8rem; color:gray;">{time}
                             </div></di v>""", unsafe_allow_html=True)
                    st.write("")
            
            # gTTS를 활용하여 음성 파일 생성 및 재생
            TTS(response)
            
if __name__ =="__main__":
    main()

