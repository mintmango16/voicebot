import streamlit as st
import openai
import os
from datetime import datetime
from gtts import gTTS
import base64
import io
from streamlit_webrtc import webrtc_streamer, WebRtcMode # AudioProcessorBase는 필요 없을 수 있음
# import numpy as np # 현재 사용하지 않음
# import collections # 현재 사용하지 않음

# AudioBufferProcessor 클래스 삭제 (필요 없음)

# Streamlit UI 및 기능 함수
def STT(audio_bytes, apikey):
    # Whisper API가 WebM (Opus) 오디오를 직접 처리할 수 있는지 확인해야 함
    # 이 부분은 여전히 FFmpeg 문제가 발생할 수 있는 잠재적 위험 구간입니다.
    # streamlit-webrtc가 녹음된 최종 파일을 직접 반환하는 것이 아님.
    # audio_bytes가 실제로 WebM 형식의 오디오 데이터인지 확신하기 어려움.
    
    # -------------------------------------------------------------
    # **가장 중요한 부분:**
    # streamlit-webrtc는 녹음된 '파일'을 직접 반환하지 않습니다.
    # webrtc_ctx.audio_receiver를 통해 실시간 프레임을 받아서
    # PyAV (ffmpeg 필요) 등으로 직접 인코딩하여 파일로 만들어야 합니다.
    # 현재 코드로는 audio_bytes에 유효한 녹음 데이터가 들어가지 않습니다.
    # 이 코드는 STT 함수가 호출될 때 `audio_bytes`에 실제 데이터가 있을 것이라고
    # 가정하고 작성되었지만, webrtc_streamer 컴포넌트 자체의 API만으로는
    # 녹음 완료 시점에 최종 오디오 파일을 얻기가 매우 어렵습니다.
    # -------------------------------------------------------------

    # 임시 파일로 저장 (Whisper API가 파일 경로를 요구할 수 있음)
    # Whisper API는 파일 객체를 직접 받으므로 파일로 저장 후 열기
    # 현재 audio_bytes는 사실상 비어있을 가능성이 높습니다.
    if not audio_bytes: # audio_bytes가 비어있으면 오류 방지
        return "STT 오류: 녹음된 오디오 데이터가 없습니다."

    filename = "input.webm" # webrtc는 기본적으로 webm (opus) 포맷
    try:
        with open(filename, "wb") as f:
            f.write(audio_bytes)

        audio_file = open(filename, "rb")

        client = openai.OpenAI(api_key = apikey)
        respons = client.audio.transcriptions.create(model="whisper-1", file = audio_file)
        text_response = respons.text

    except Exception as e:
        text_response = f"STT 오류 발생: {e}. 오디오 데이터 처리 또는 Whisper API 호출 문제."
        st.error(text_response)
    finally:
        if 'audio_file' in locals() and not audio_file.closed:
            audio_file.close()
        if os.path.exists(filename):
            os.remove(filename)
    return text_response

def ask_gpt(prompt, model, apikey):
    client = openai.OpenAI(api_key= apikey)
    response = client.chat.completions.create(
        model = model,
        messages= prompt)
    gptResponse = response.choices[0].message.content
    return gptResponse

def TTS(response):
    tts = gTTS(text=response, lang = "ko")
    
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    st.audio(mp3_fp.getvalue(), format="audio/mp3", autoplay=True)

## 메인 함수 ##
def main():
    st.set_page_config(
        page_title = "음성 비서 프로그램",
        layout  = "wide")

    st.header("🔊 250611_음성 비서 프로그램 실습")

    st.markdown("---")

    with st.expander("음성 비서 프로그램?", expanded = True):
        st.write(
        """
        - 음성 비서 프로그램의 UI는 Streamlit을 활용했습니다.
        - STT (Speech-to-text) : OpenAI의 Wisper AI
        - 답변 : OpenAI의 GPT
        - TTS (Text-to-Speech) : 구글의 Google Translate TTS
        - 마이크 입력: `streamlit-webrtc` 활용
        """
        )
        st.markdown("---")

    if "chat" not in st.session_state :
        st.session_state["chat"]=[]
        
    if "OPENAI_API" not in st.session_state :
        st.session_state["OPENAI_API"]=""
        
    if "messages" not in st.session_state :
        st.session_state["messages"]=[{"role": "system", "content":"You are a thoughtful assistant. Respond to all input in 25 words and answer in korean"}]
    
    if "check_reset" not in st.session_state :
        st.session_state["check_reset"]=False

    with st.sidebar:
        st.session_state["OPENAI_API"] = st.text_input(label = "OPENAI API 키",
                                                       placeholder = "Enter Your API key",
                                                       value = st.session_state["OPENAI_API"],
                                                       type = "password")
        st.markdown("---")
        
        model = st.radio(label = "GPT 모델", options = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"])
        st.markdown("---")
        
        if st.button(label = "초기화"):
            st.session_state["chat"] = []
            st.session_state["messages"] = [{"role": "system", "content":"You are a thoughtful assistant. Respond to all input in 25 words and answer in korean"}]
            st.session_state["check_reset"]= True
            st.rerun()

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("질문하기")
        st.info("아래 'Start' 버튼을 눌러 마이크 스트림을 시작하고, 'Stop' 버튼을 누르면 종료됩니다.")

        # streamlit-webrtc 스트림 컴포넌트
        webrtc_ctx = webrtc_streamer(
            key="voice_assistant",
            mode=WebRtcMode.SENDONLY, # 오디오만 보냄
            audio_receiver_size=1024 * 1024, # 녹음 버퍼 크기 (1MB) - 실제 파일 저장 용도가 아님
            media_stream_constraints={"video": False, "audio": True}, # 비디오는 끄고 오디오만 켮
        )
        
        audio_bytes = None
        # 스트림이 활성화 되어 있는 동안
        if webrtc_ctx.state.playing:
            st.write("🔴 녹음 중...")
            # webrtc_ctx.audio_receiver에서 프레임을 가져오는 것은 실시간 처리용입니다.
            # 녹음이 '끝났을 때' 오디오 데이터를 얻는 방식이 아님.
            # 이 코드 블록 안에서는 녹음된 바이트를 얻을 수 없음.
            
        # 스트림이 비활성화 되어 있고, 이전에 재생된 적이 있다면 (즉, 'Stop'을 눌렀을 때)
        # 이 부분이 가장 복잡하며, webrtc-streamlit의 기본적인 한계점.
        # webrtc_ctx.audio_receiver.get_buffered_frames()는 실시간 버퍼이므로
        # 스트림이 끊어지면 데이터가 유실되거나 접근하기 어려울 수 있음.
        # 따라서 `streamlit-webrtc` 공식 예제 중 녹음 후 파일 저장하는 방식은
        # 대부분 JS로 클라이언트 측에서 처리하거나, 서버에서 프레임을 계속 받는 방식.
        # 즉, 이 조건문 안에서 `audio_bytes`를 채우는 것은 매우 어렵습니다.
        
        # 해결책: 세션 상태에 버퍼를 저장하고, `playing`이 False가 될 때 처리
        # 이 방법도 PyAV나 다른 오디오 처리 라이브러리가 필요함 (FFmpeg 의존성)
        # 따라서 가장 현실적인 접근은 `st.file_uploader` 입니다.
        
        # --- 임시적인 STT 호출 로직 (실제 오디오 데이터가 아님) ---
        # 실제로는 webrtc_ctx에서 녹음된 오디오 데이터를 직접 가져오기 어렵습니다.
        # 이 부분은 `st.file_uploader`를 사용하거나, `streamlit-webrtc`의
        # 더 복잡한 예제 (JS 연동 등)를 참고해야 합니다.
        # 현재는 STT 함수를 호출하기 위해 임시로 비어있는 바이트를 전달합니다.
        # 따라서 이 코드로는 마이크 녹음-STT-GPT-TTS 체인이 동작하지 않습니다.
        
        # `streamlit-webrtc`의 `state.playing`이 `False`가 되는 순간은
        # 앱 로드 시점, 또는 사용자가 'Stop' 버튼을 눌렀을 때.
        # 이 때 STT를 호출하기 위한 오디오 데이터를 얻는 것이 핵심인데,
        # `streamlit-webrtc` 컴포넌트 자체는 '녹음된 파일'을 반환하지 않습니다.
        # 이 때문에 `audio_bytes`는 계속 비어있거나, 이전 데이터가 남아있을 수 있습니다.
        
        # `streamlit-audiorecorder`가 'record and send' 개념이었다면,
        # `streamlit-webrtc`는 'stream and process' 개념입니다.
        # 이 차이 때문에 마이크 녹음 -> STT로의 직접적인 연결이 어렵습니다.
        
        # 이 예시 코드는 STT 함수를 호출할 수 있도록 구조를 맞췄지만,
        # 실제 마이크 녹음 데이터가 STT로 전달되지는 않을 것입니다.
        
        # 만약 webrtc_ctx.audio_receiver.get_buffered_frames()를 통해 데이터를 얻고 싶다면,
        # 이는 PyAV 등을 통해 WebM으로 인코딩하는 별도의 복잡한 로직이 필요하며,
        # PyAV 설치 시 FFmpeg 문제가 다시 발생할 수 있습니다.
        
        # 따라서 아래 STT 호출은 **실제 마이크 녹음 데이터가 아님**을 인지해야 합니다.
        # 이 코드를 실행하면 STT가 "녹음된 오디오 데이터가 없습니다" 또는 유사한 오류를 반환할 가능성이 높습니다.
        
        if not webrtc_ctx.state.playing and webrtc_ctx.audio_receiver: # 'playing'이 false이고, receiver가 활성화된 적이 있다면
            # 이 로직은 `streamlit-webrtc`의 실제 사용 패턴과 다릅니다.
            # 실제로는 `audio_receiver`에서 프레임을 계속 받아 처리하는 별도의 스레드/프로세스가 필요합니다.
            st.warning("`streamlit-webrtc`에서 녹음된 오디오 데이터를 직접 가져오는 것은 복잡합니다. 이 부분은 STT를 테스트하기 위한 예시이며, 실제 마이크 녹음 데이터가 아닐 수 있습니다.")
            audio_bytes = b"" # 임시로 빈 바이트를 전달
            # 실제 데이터를 얻으려면 다음과 같은 복잡한 과정이 필요합니다.
            # 1. webrtc_ctx.audio_receiver에서 `get_buffered_frames()` 또는 `consume_buffered_frames()`를 지속적으로 호출
            # 2. PyAV를 사용하여 이 프레임들을 WebM 컨테이너로 인코딩하여 메모리에 저장
            # 3. 녹음 종료 시, 메모리의 WebM 데이터를 최종 audio_bytes로 사용

        if audio_bytes is not None and (st.session_state["check_reset"]==False):
            if audio_bytes: # 실제로 데이터가 있을 때만 STT 시도 (현재는 거의 없을 것임)
                question = STT(audio_bytes, st.session_state["OPENAI_API"])
                
                now = datetime.now().strftime("%H:%M")
                st.session_state["chat"] = st.session_state["chat"]+[("user", now, question)]
                st.session_state["messages"] = st.session_state["messages"]+[{"role": "user", "content": question}]
            else:
                st.info("녹음된 오디오 데이터가 없습니다.") # 이 메시지가 계속 뜰 것입니다.

    with col2:
        st.subheader("답변")
        
        # `streamlit-webrtc`의 'Stop' 버튼 클릭 후 STT가 처리될 때 GPT 호출
        # `webrtc_ctx.state.playing`이 `False`이면서
        # 마지막 유저 메시지가 있고, 리셋 상태가 아닐 때.
        if not webrtc_ctx.state.playing and (st.session_state['check_reset']==False) and \
           st.session_state["messages"][-1]["role"] == "user": # 마지막 메시지가 사용자 질문일 경우만
            
            response = ask_gpt(st.session_state['messages'], model,
                                 st.session_state["OPENAI_API"])
            
            st.session_state["messages"] = st.session_state["messages"] + [{"role":"assistant", "content" : response}]
            
            now = datetime.now().strftime("%H:%M")
            st.session_state["chat"] = st.session_state["chat"] + [("bot", now, response)]
            
            for sender, time, message in st.session_state["chat"] : 
                if sender == "user":
                    st.write(f"""<div style="display :flex;align-items:center;">
                                 <div style="background-color: #007AFF; color:white;border-radius:12px;
                                 padding:8px 12px;margin-right :8px; ">{message}</div>
                                 <div style="font-size :0.8rem;color:gray;">{time}</div></div>""",
                                 unsafe_allow_html=True)
                    st.write("")
                else : 
                    st.write(f"""<div style="display:flex; align-items:center; justify-content:flex-end;">
                                 <div style="background-color:lightgray; border-radius:12px; padding :8px 12px;
                                 margin-left :8px;">{message}</div><div style="font-size:0.8rem; color:gray;">{time}
                                 </div></div>""", unsafe_allow_html=True)
                    st.write("")
            
            TTS(response)
        elif st.session_state['check_reset']:
            st.info("초기화되었습니다.")
        elif not webrtc_ctx.state.playing: # 스트림이 시작되지 않았거나 멈춘 경우
            st.info("녹음을 시작해주세요.")


if __name__ =="__main__":
    main()
