import streamlit as st
import openai
import os
from datetime import datetime
from gtts import gTTS
import base64
import io
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import numpy as np
import collections # 오디오 버퍼링을 위해 deque 사용

# PyAV를 사용한 오디오 처리 시 필요한 모듈 (Streamlit Cloud에서 설치될지 미지수)
# import av # 주석 처리: 설치 실패 가능성 때문에 일단 제외

# 오디오 버퍼를 저장할 클래스 (streamlit-webrtc 예제에서 차용)
class AudioBufferProcessor(AudioProcessorBase):
    def __init__(self):
        self.audio_buffer = collections.deque()
        self.start_recording_time = None
        self.is_recording = False

    def recv(self, frame):
        # frame.to_ndarray()는 float 형태의 NumPy 배열을 반환
        # Whisper API는 WAV 바이트를 선호하므로, 여기에 쌓는 것은 적절치 않을 수 있음
        # 스트림 자체를 저장하여 나중에 처리하는 것이 더 나음
        # 일단은 무시하고, 녹음 종료 시점에 전체 스트림을 얻는 방향으로 접근

        # 실제로 오디오 데이터를 처리할 필요가 없다면 이 함수는 비워둘 수 있음
        # 하지만 Streamlit Cloud 환경에서 녹음된 오디오 스트림을 얻는 방식이 중요함.
        # webrtc_streamer는 최종적으로 audio_receiver를 통해 데이터를 접근하게 됨.
        return frame

# Streamlit UI 및 기능 함수
def STT(audio_bytes, apikey):
    # Streamlit-webrtc에서 받은 raw bytes를 Whisper API로 전달
    # Whisper API가 WebM (Opus) 오디오를 직접 처리할 수 있는지 확인해야 함
    # 만약 안 된다면, 여기에 ffmpeg-python 등으로 WAV로 변환하는 로직이 필요하나,
    # 이는 Streamlit Cloud에서 FFmpeg 문제로 다시 막힐 가능성이 매우 높음.
    # 일단은 WebM을 직접 보내는 것을 시도.

    # 임시 파일로 저장 (Whisper API가 파일 경로를 요구할 수 있음)
    # Whisper API는 파일 객체를 직접 받으므로 파일로 저장 후 열기
    filename = "input.webm" # webrtc는 기본적으로 webm (opus) 포맷
    with open(filename, "wb") as f:
        f.write(audio_bytes)

    audio_file = open(filename, "rb")

    client = openai.OpenAI(api_key = apikey)
    try:
        respons = client.audio.transcriptions.create(model="whisper-1", file = audio_file)
        text_response = respons.text
    except Exception as e:
        text_response = f"STT 오류 발생: {e}. WebM 포맷이 Whisper API에 호환되는지 확인해주세요."
        st.error(text_response)

    audio_file.close()
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
    filename = "output.mp3"
    tts = gTTS(text=response, lang = "ko")
    
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    st.audio(mp3_fp.getvalue(), format="audio/mp3", autoplay=True)
    # os.remove(filename) # 이제 필요 없음

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
        st.session_state["OPENAI_API"]="" # API 키는 문자열로 초기화
        
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
        
        model = st.radio(label = "GPT 모델", options = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]) # 최신 모델로 변경
        st.markdown("---")
        
        if st.button(label = "초기화"):
            st.session_state["chat"] = []
            st.session_state["messages"] = [{"role": "system", "content":"You are a thoughtful assistant. Respond to all input in 25 words and answer in korean"}]
            st.session_state["check_reset"]= True
            st.rerun()

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("질문하기")
        st.info("아래 'Start' 버튼을 눌러 녹음을 시작하고, 'Stop' 버튼을 누르면 녹음이 중지됩니다.")

        # streamlit-webrtc 스트림 컴포넌트
        # 오디오 트랙만 필요하므로 video_receiver_size=0
        webrtc_ctx = webrtc_streamer(
            key="voice_assistant",
            mode=WebRtcMode.SENDONLY, # 오디오만 보냄
            audio_receiver_size=1024 * 1024, # 녹음 버퍼 크기 (1MB)
            media_stream_constraints={"video": False, "audio": True}, # 비디오는 끄고 오디오만 켮
            # rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}, # NAT 트래버설을 위한 STUN 서버 (선택 사항)
            # audio_processor_factory=AudioBufferProcessor # 오디오 데이터를 직접 처리할 필요가 없다면 주석 처리
        )
        
        audio_bytes = None
        if webrtc_ctx.state.playing:
            st.write("🔴 녹음 중...")
            # 여기서는 녹음 중인 상태만 표시. 실제 오디오 데이터는 webrtc_ctx.audio_receiver.get_buffered_frames() 등을 통해 얻어야 함.
            # 하지만 webrtc_streamer 컴포넌트가 STOP될 때 녹음된 오디오를 얻는 방식이 더 간편함.
            # webrtc_streamer는 기본적으로 녹음된 오디오 스트림(WebM)을 반환할 수 있음.
        elif webrtc_ctx.state.ended:
            st.write("✅ 녹음 완료!")
            # 녹음이 종료되었을 때만 audio_receiver로부터 데이터를 가져옴
            if webrtc_ctx.audio_receiver:
                try:
                    # audio_receiver로부터 buffered_frames를 가져옴 (Opus 코덱의 WebM 스트림)
                    # Streamlit-webrtc의 get_buffered_frames()는 AVFrame 리스트를 반환함
                    # 이것들을 하나로 합쳐서 WebM 파일로 저장해야 Whisper API에 전달 가능함.
                    # PyAV를 사용해야 하는데, Streamlit Cloud에서 PyAV 설치가 복잡할 수 있음.
                    # 만약 PyAV가 설치된다면, 아래 주석 처리된 PyAV 관련 코드를 활성화하세요.
                    # -------------------------------------------------------------
                    # 임시로 streamlit-webrtc 자체의 녹음 기능이 제공하는 방식으로 시도.
                    # webrtc_streamer는 현재 녹음된 바이트를 직접 반환하는 기능이 없음.
                    # 즉, 별도의 처리 로직이 필요하다는 뜻.
                    # 가장 간단한 해결책은 Streamlit Discussions의 webrtc 예제처럼
                    # 녹음된 세션을 저장하여 나중에 STT 처리하는 것.
                    # 아래는 Streamlit-webrtc 예제에서 흔히 볼 수 있는 오디오 캡처 방식 (PyAV 필요)
                    
                    # 이 부분이 Streamlit Cloud에서 가장 큰 걸림돌이 될 수 있습니다.
                    # PyAV 라이브러리도 C/C++ 컴파일러와 FFmpeg 개발 헤더가 필요할 수 있기 때문입니다.
                    # 만약 PyAV 설치가 안 되면, 이 방식도 실패합니다.
                    
                    # ----- PyAV를 이용한 오디오 처리 예시 (설치 성공 시) -----
                    # frames = webrtc_ctx.audio_receiver.get_buffered_frames()
                    # if frames:
                    #     with io.BytesIO() as out_buffer:
                    #         # PyAV를 사용하여 WebM으로 인코딩
                    #         container = av.open(out_buffer, mode="w", format="webm")
                    #         stream = container.add_stream("libopus", rate=48000)
                    #         stream.layout = "stereo" if frames[0].layout.name == "stereo" else "mono"
                    #         stream.bit_rate = 128000
                    #         for frame in frames:
                    #             for packet in stream.encode(frame):
                    #                 container.mux(packet)
                    #         for packet in stream.encode():
                    #             container.mux(packet)
                    #         container.close()
                    #         audio_bytes = out_buffer.getvalue()
                    # --------------------------------------------------------

                    # PyAV 없이 webrtc_streamer에서 녹음된 오디오를 직접 얻는 단순화된 방식 (정상 작동 보장 어려움)
                    # 현재 webrtc_streamer는 녹음된 '파일'을 직접 반환하는 API가 없음.
                    # 따라서 클라이언트에서 녹음된 오디오를 서버로 전송하는 별도의 로직 필요.
                    # 예를 들어 JavaScript 콜백을 통해 base64 인코딩된 데이터를 Streamlit으로 보내는 방식.
                    # 이는 현재 코드 구조에서 벗어남.
                    
                    # 가장 단순한 접근은: Streamlit-webrtc의 상태 변화를 감지하고,
                    # 녹음이 완료된 시점에 클라이언트에서 오디오를 획득하여 서버로 보내는 것인데,
                    # 이는 webrtc_streamer 컴포넌트 자체의 API로 직접 지원되지 않음.
                    # 그래서 대부분의 webrtc 예제는 오디오/비디오 트랙을 직접 처리하는 로직을 포함.
                    
                    # 이 코드에서는 webrtc_streamer 컴포넌트가 "stopped" 상태일 때
                    # 오디오 데이터가 존재한다고 가정하고 STT를 시도.
                    # (실제 데이터 획득은 webrtc_ctx.audio_receiver에서 복잡하게 이루어져야 함)
                    # 이 부분은 실제로는 작동하지 않을 가능성이 높습니다.
                    # 왜냐하면 webrtc_ctx.audio_receiver.get_buffered_frames()는
                    # 실시간 스트림 처리용이지, "녹음된 파일"을 반환하는 용도가 아니기 때문입니다.
                    # 따라서 이 코드를 실행하면 STT 단계에서 오류가 날 가능성이 높습니다.

                    # --- 대안: 스트림이 종료될 때, 브라우저에서 서버로 오디오 데이터 전송 ---
                    # 하지만 Streamlit의 Python 코드만으로는 복잡한 JS/WebRTC 녹음 완료 데이터 전송을 구현하기 어렵습니다.
                    # 이 때문에 'streamlit-audiorecorder'와 같은 더 단순한 라이브러리가 선호되었던 것입니다.

                    st.warning("`streamlit-webrtc`에서 녹음된 오디오 데이터를 직접 가져오는 로직은 복잡합니다. 아래 STT는 예시이며, 실제 작동하지 않을 수 있습니다.")
                    st.warning("이 부분에서 오류가 발생하면 `streamlit-webrtc`를 이용한 실시간 마이크 녹음은 Streamlit Cloud에서 매우 어렵다는 의미입니다. `st.file_uploader`를 사용하세요.")
                    
                    # 임시 방편으로, 오디오 스트림이 종료되면
                    # 어떤 오디오 데이터가 있다고 가정하고 STT를 호출 (실제 데이터는 비어있을 것)
                    # 실제 webrtc_streamer의 오디오 데이터를 얻는 방식은 복잡합니다.
                    # 이는 PyAV를 이용하거나, 커스텀 컴포넌트를 만들어 JS에서 녹음된 데이터를
                    # Streamlit으로 전송해야 합니다.
                    # 이 때문에 결국 'file_uploader' 방식이 가장 현실적입니다.
                    
                    # --- 임시적인 STT 호출 로직 (실제 오디오 데이터가 아님) ---
                    # webrtc_streamer가 녹음된 오디오를 바이트로 직접 반환하지 않으므로
                    # 이 부분은 STT 테스트를 위해 임시로 비워두거나,
                    # `ffmpeg-python` 등을 통한 복잡한 변환 로직이 들어가야 함.
                    # 이대로 실행하면 `audio_bytes`는 None이거나 비어있을 것임.
                    audio_bytes = b"" # 일단 빈 바이트로 설정하거나, 파일 업로더를 병행 사용
                    # ----------------------------------------------------

                except Exception as e:
                    st.error(f"오디오 스트림 처리 오류: {e}. PyAV 설치 및 FFmpeg 관련 문제일 수 있습니다.")
                    audio_bytes = None
            else:
                audio_bytes = None # 녹음 중이 아니면 audio_bytes는 None

        if audio_bytes is not None and (st.session_state["check_reset"]==False):
            if audio_bytes: # 실제로 데이터가 있을 때만 STT 시도
                question = STT(audio_bytes, st.session_state["OPENAI_API"])
                
                now = datetime.now().strftime("%H:%M")
                st.session_state["chat"] = st.session_state["chat"]+[("user", now, question)]
                st.session_state["messages"] = st.session_state["messages"]+[{"role": "user", "content": question}]
            else:
                st.info("녹음된 오디오 데이터가 없습니다.") # 데이터가 비어있을 경우 메시지

    with col2:
        st.subheader("답변")
        
        # webrtc_ctx.state.ended는 녹음이 중지된 상태를 의미
        # 녹음이 중지되었고, 리셋되지 않았을 때만 GPT 호출
        if webrtc_ctx.state.ended and (st.session_state['check_reset']==False) :
            if st.session_state["messages"][-1]["role"] == "user": # 마지막 메시지가 사용자 질문일 경우만
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
            else:
                st.info("GPT 답변 대기 중이거나 이미 답변이 완료되었습니다.")
        elif st.session_state['check_reset']:
            st.info("초기화되었습니다.")
        else:
            st.info("녹음을 시작해주세요.")

if __name__ =="__main__":
    main()
