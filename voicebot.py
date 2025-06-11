#streamlit run voicebot.py
import streamlit as st
# from audiorecorder import audiorecorder # <-- 이 줄을 주석 처리하거나 삭제합니다.
from streamlit_audiorecorder import st_audiorec # <-- 이 줄을 새로 추가합니다.

import openai
import os
from datetime import datetime
from gtts import gTTS
import base64
import io # <-- BytesIO를 사용하기 위해 추가합니다.

## 기능 구현 함수 ##
def STT(audio_bytes, apikey): # 오디오 입력 타입을 bytes로 변경합니다.
    # audiorecorder가 반환하는 객체가 아닌 raw bytes를 처리하도록 수정
    filename = "input.mp3"
    # audio.export(filename, format = "mp3") # audiorecorder 객체가 아니므로 이 줄은 삭제합니다.
    
    # st_audiorec이 반환하는 WAV 바이트를 파일로 저장
    with open(filename, "wb") as f:
        f.write(audio_bytes) # <-- WAV 바이트를 파일로 저장합니다.

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
    # filename = "output.mp3" # 이제 직접 파일을 저장하지 않고 메모리에서 처리
    tts = gTTS(text=response, lang = "ko")
    
    # 음원 파일을 메모리에 저장 (파일 시스템에 직접 저장하지 않음)
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0) # 스트림의 시작으로 커서를 이동

    # Streamlit의 st.audio를 사용하여 음원 재생
    st.audio(mp3_fp.getvalue(), format="audio/mp3", autoplay=True) # <-- autoplay=True 추가
    
    # 파일 삭제 로직은 이제 필요 없습니다. (메모리에서 처리)
    # os.remove(filename)


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
        st.session_state["OPENAI_API"]="" # API 키는 문자열로 초기화
        
    if "messages" not in st.session_state :
        st.session_state["messages"]=[{"role": "system", "content":"You are a thoughtful assistant. Respond to all input in 25 words and answer in korean"}] # 'korea'를 'korean'으로 수정
    
    if "check_reset" not in st.session_state : # check_audio 대신 check_reset으로 수정
        st.session_state["check_reset"]=False

      # 사이드바 생성
    with st.sidebar:
        st.session_state["OPENAI_API"] = st.text_input(label = "OPENAI API 키",
                                                       placeholder = "Enter Your API key",
                                                       value = st.session_state["OPENAI_API"], # 초기값 설정
                                                       type = "password")
        st.markdown("---")
        
        model = st.radio(label = "GPT 모델", options = ["gpt-4", "gpt-4o", "gpt-3.5-turbo"]) # gpt-4.1-mini는 일반적인 모델이 아니므로 적절한 모델로 변경 (예: gpt-3.5-turbo, gpt-4o 등)
        st.markdown("---")
        
        if st.button(label = "초기화"):
            #리셋 코드
            st.session_state["chat"] = []
            st.session_state["messages"] = [{"role": "system", "content":"You are a thoughtful assistant. Respond to all input in 25 words and answer in korean"}]
            st.session_state["check_reset"]= True
            st.rerun() # 초기화 후 페이지를 새로고침하여 상태 반영

    # 기능 구현 공간
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("질문하기")
        #음성 녹음 아이콘
        # audiorecorder 대신 st_audiorec 사용
        audio_bytes = st_audiorec(start_text="클릭하여 녹음 시작", stop_text="녹음 중지") # st_audiorec 반환값은 bytes
        
        if audio_bytes is not None and (st.session_state["check_reset"]==False) : # audio.duration_seconds > 0 대신 audio_bytes가 None이 아닌지 확인
            # 녹음 실행시
            # 음성 재생 (st_audiorec이 반환하는 WAV 바이트를 직접 재생)
            st.audio(audio_bytes, format="audio/wav") # <-- 녹음된 원본 WAV 바이트를 재생합니다.
            
            # 음원 파일에서 텍스트 추출
            question = STT(audio_bytes, st.session_state["OPENAI_API"]) # audio 객체 대신 audio_bytes 전달

            # 채팅을 시각화하기 위한 질문 내용 저장
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"]+[("user", now, question)] # 'sesstion_state' 오타 수정
            # GPT 모델에 넣을 프롬프트를 위해 질문 내용 저장
            st.session_state["messages"] = st.session_state["messages"]+[{"role": "user", "content": question}]

    with col2:
        st.subheader("답변")
        
        # 오디오가 녹음되었을 때만 GPT 호출 및 답변 처리
        # `audio_bytes is not None`과 `check_reset`을 함께 확인
        if audio_bytes is not None and (st.session_state['check_reset']==False) :
            # chatGPT에게 답변 얻기
            response = ask_gpt(st.session_state['messages'], model,
                                 st.session_state["OPENAI_API"])
            
            # GPT 모델에 넣을 프롬프트를 위해 답변 내용 저장
            st.session_state["messages"] = st.session_state["messages"] + [{"role":"assistant", "content" : response}] # role을 "assistant"로 변경하는 것이 더 적절합니다.
            
            # 채팅 시각화를 위한 답변 내용 저장
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"] + [("bot", now, response)]
            
            # 채팅 형식으로 시각화 하기
            for sender, time, message in st.session_state["chat"] :
                if sender == "user": # 대화 주체가 사용자 = 질문 파란색
                    st.write(f"""<div style="display :flex;align-items:center;">
                                 <div style="background-color: #007AFF; color:white;border-radius:12px;
                                 padding:8px 12px;margin-right :8px; ">{message}</div>
                                 <div style="font-size :0.8rem;color:gray;">{time}</div></div>""",
                                 unsafe_allow_html=True)
                    st.write("") # 줄바꿈을 위해 빈 st.write 추가
                else : # 대화 주체가 gpt = 답변 회색
                    st.write(f"""<div style="display:flex; align-items:center; justify-content:flex-end;">
                                 <div style="background-color:lightgray; border-radius:12px; padding :8px 12px;
                                 margin-left :8px;">{message}</div><div style="font-size:0.8rem; color:gray;">{time}
                                 </div></div>""", unsafe_allow_html=True)
                    st.write("") # 줄바꿈을 위해 빈 st.write 추가
            
            # gTTS를 활용하여 음성 파일 생성 및 재생
            TTS(response)

# 초기화 버튼을 눌렀을 때만 페이지 새로고침
# if st.session_state["check_reset"]: # 이 부분은 이제 필요 없습니다. 초기화 버튼 안에 st.rerun()을 넣었습니다.
#     st.session_state["check_reset"] = False # 리셋 상태 초기화
#     st.rerun() # 페이지 새로고침
            
if __name__ =="__main__":
    main()