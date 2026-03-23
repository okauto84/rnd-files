# -*- coding: utf-8 -*-

import streamlit as st
from openai import OpenAI
import time

# 페이지 설정
st.set_page_config(
    page_title="Structure",
    page_icon="💬",
    layout="wide"
)

# API 키 설정
try:
    API_KEY = st.secrets.get("openai_api_key", "")
except:
    API_KEY = ""

model_name = "gpt-5.4"

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 챗봇 섹션
st.markdown("#### 💬 챗봇")


def call_openai_api(messages: list) -> str:
    try:
        if not API_KEY or API_KEY == "":
            return "⚠️ API 키가 설정되지 않았습니다. Streamlit secrets의 openai_api_key를 설정해주세요."

        client = OpenAI(api_key=API_KEY)

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )

        return response.choices[0].message.content

    except Exception as e:
        error_msg = str(e)
        if "API_KEY" in error_msg or "authentication" in error_msg.lower() or "invalid" in error_msg.lower():
            return f"🔑 API 키 오류: API 키를 확인해주세요.\n\n에러 상세: {error_msg}"
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower() or "rate" in error_msg.lower():
            return f"📊 사용량 한도 초과: API 사용량을 확인해주세요.\n\n에러 상세: {error_msg}"
        else:
            return f"❌ API 호출 중 오류가 발생했습니다: {error_msg}"


# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("질문해보세요!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        messages_for_api = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in st.session_state.messages
        ]

        with st.spinner("생성AI가 답변을 생성하고 있습니다..."):
            response = call_openai_api(messages_for_api)

        message_placeholder = st.empty()
        displayed_text = ""
        for char in response:
            displayed_text += char
            message_placeholder.markdown(displayed_text + "▌")
            time.sleep(0.01)
        message_placeholder.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

# API 키 안내
if not API_KEY or API_KEY == "":
    st.warning("⚠️ OpenAI API 키가 설정되지 않았습니다. Streamlit secrets를 확인해주세요.")
