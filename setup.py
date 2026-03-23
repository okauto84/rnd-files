# -*- coding: utf-8 -*-

import os
import time
import pathlib
import pandas as pd
import streamlit as st
from openai import OpenAI


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


# ── 디렉토리 트리 ──────────────────────────────────────────────────────────────

def build_tree(path: pathlib.Path) -> dict:
    """경로를 재귀적으로 읽어 트리 구조 dict 반환.
    디렉토리는 children 리스트를 포함하며, 파일은 포함하지 않는다.
    """
    node = {
        "name": path.name or str(path),
        "type": "dir" if path.is_dir() else "file",
        "path": str(path),
    }
    if path.is_dir():
        children = []
        try:
            entries = sorted(
                path.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower())
            )
            for child in entries:
                children.append(build_tree(child))
        except PermissionError:
            pass
        node["children"] = children
    return node


def render_tree_native(node: dict, depth: int = 0):
    """트리를 Streamlit 네이티브 컴포넌트로 렌더링.
    - 폴더: st.expander (CSS로 +/- 표시)
    - .md/.csv 파일: st.button (클릭 시 session_state에 경로 저장)
    - 기타 파일: 일반 텍스트
    """
    name = node["name"]
    ext = pathlib.Path(name).suffix.lower()

    if node["type"] == "dir":
        child_count = len(node.get("children", []))
        with st.expander(f"📁 {name}  ({child_count})", expanded=(depth == 0)):
            for child in node.get("children", []):
                render_tree_native(child, depth + 1)
    else:
        icon = _file_icon(name)
        if ext in (".md", ".csv"):
            if st.button(
                f"{icon} {name}",
                key=f"filebtn_{node['path']}",
                use_container_width=False,
            ):
                st.session_state.selected_file = node["path"]
                st.session_state.selected_file_ext = ext
        else:
            st.markdown(
                f'<p style="margin:1px 0; padding:1px 4px; font-size:0.82rem; '
                f'font-family:monospace; color:#555;">{icon} {name}</p>',
                unsafe_allow_html=True,
            )


def _file_icon(filename: str) -> str:
    """확장자별 파일 아이콘 반환."""
    ext = pathlib.Path(filename).suffix.lower()
    icons = {
        ".py": "🐍", ".js": "🟨", ".ts": "🔷", ".tsx": "🔷", ".jsx": "🟨",
        ".html": "🌐", ".css": "🎨", ".json": "📋", ".yaml": "📋", ".yml": "📋",
        ".md": "📝", ".txt": "📄", ".csv": "📊", ".xlsx": "📊", ".xls": "📊",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".gif": "🖼️", ".svg": "🖼️",
        ".pdf": "📕", ".zip": "📦", ".tar": "📦", ".gz": "📦",
        ".sh": "⚙️", ".bat": "⚙️", ".toml": "⚙️", ".cfg": "⚙️", ".ini": "⚙️",
        ".env": "🔑", ".gitignore": "🚫",
    }
    return icons.get(ext, "📄")


# 현재 스크립트 위치를 루트로 사용
BASE_DIR = pathlib.Path(os.path.abspath(__file__)).parent

# 세션 상태 초기화 (선택 파일)
if "selected_file" not in st.session_state:
    st.session_state.selected_file = None
    st.session_state.selected_file_ext = None

# ── 트리 CSS ──────────────────────────────────────────────────────────────────
# expander 기본 화살표 숨기고 +/- 배지로 대체 / 파일 버튼을 링크처럼 스타일
st.markdown("""
<style>
  /* 기본 expander 화살표 숨김 */
  [data-testid="stExpander"] details summary svg { display: none !important; }

  /* +/- 배지 */
  [data-testid="stExpander"] details > summary::before {
    content: "+";
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    font-size: 0.82rem;
    font-weight: bold;
    color: #555;
    background: #e9ecef;
    border: 1px solid #ced4da;
    border-radius: 3px;
    margin-right: 6px;
    flex-shrink: 0;
  }
  [data-testid="stExpander"] details[open] > summary::before { content: "−"; }

  /* 파일 버튼: 링크 스타일 */
  [data-testid="stExpander"] [data-testid="stBaseButton-secondary"] {
    background: none !important;
    border: none !important;
    box-shadow: none !important;
    padding: 1px 4px !important;
    font-size: 0.82rem !important;
    font-family: monospace !important;
    color: #1a6cc4 !important;
    height: auto !important;
    min-height: unset !important;
    line-height: 1.5 !important;
    text-align: left !important;
  }
  [data-testid="stExpander"] [data-testid="stBaseButton-secondary"]:hover {
    color: #0044aa !important;
    background: #e8f0fe !important;
    text-decoration: underline !important;
  }
</style>
""", unsafe_allow_html=True)

st.markdown("#### 📂 디렉토리 구조")
st.caption(f"기준 경로: `{BASE_DIR}`")

# 트리 데이터를 변수에 저장
tree_data: dict = build_tree(BASE_DIR)

# 계층 구조(트리) 화면 출력
render_tree_native(tree_data, depth=0)

# ── 선택된 파일 내용 표시 ────────────────────────────────────────────────────
if st.session_state.selected_file:
    fp = pathlib.Path(st.session_state.selected_file)
    ext = st.session_state.selected_file_ext

    st.markdown("---")
    col_title, col_close = st.columns([11, 1])
    with col_title:
        st.markdown(f"##### 📄 {fp.name}")
        st.caption(str(fp))
    with col_close:
        if st.button("✕ 닫기", key="close_preview"):
            st.session_state.selected_file = None
            st.session_state.selected_file_ext = None
            st.rerun()

    if ext == ".md":
        try:
            content = fp.read_text(encoding="utf-8")
            st.markdown(content)
        except Exception as e:
            st.error(f"파일을 읽을 수 없습니다: {e}")

    elif ext == ".csv":
        try:
            df = pd.read_csv(str(fp))
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"파일을 읽을 수 없습니다: {e}")

st.markdown("---")


# ── 챗봇 ──────────────────────────────────────────────────────────────────────

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("#### 💬 Q&A")


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
