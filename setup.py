# -*- coding: utf-8 -*-

import os
import time
import pathlib
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


def tree_to_html(node: dict, depth: int = 0) -> str:
    """트리 dict를 <details>/<summary> 기반 HTML 문자열로 변환.
    summary::before CSS로 닫힘=＋, 열림=－ 표시.
    """
    indent_px = depth * 20
    if node["type"] == "dir":
        children_html = "".join(
            tree_to_html(child, depth + 1)
            for child in node.get("children", [])
        )
        open_attr = "open" if depth == 0 else ""
        child_count = len(node.get("children", []))
        count_badge = (
            f'<span style="font-size:0.72rem;color:#888;margin-left:6px;">({child_count})</span>'
        )
        return (
            f'<details {open_attr} class="tree-node" style="margin-left:{indent_px}px; margin-top:2px;">'
            f'<summary style="cursor:pointer; padding:3px 4px; border-radius:4px; '
            f'list-style:none; display:flex; align-items:center; gap:4px; '
            f'font-size:0.88rem; user-select:none;">'
            f'<span class="tree-toggle"></span>'
            f'📁 <b>{node["name"]}</b>{count_badge}'
            f'</summary>'
            f'<div style="border-left:1px dashed #ccc; margin-left:12px; padding-left:4px;">'
            f'{children_html}'
            f'</div>'
            f'</details>'
        )
    else:
        icon = _file_icon(node["name"])
        return (
            f'<div style="margin-left:{indent_px + 20}px; padding:2px 4px; '
            f'font-size:0.85rem; color:#333;">'
            f'{icon} {node["name"]}'
            f'</div>'
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

st.markdown("#### 📂 디렉토리 구조")
st.caption(f"기준 경로: `{BASE_DIR}`")

# 트리 데이터를 변수에 저장
tree_data: dict = build_tree(BASE_DIR)

# +/- 토글 CSS
TREE_CSS = """
<style>
  .tree-toggle::before {
    content: "+";
    display: inline-block;
    width: 14px;
    height: 14px;
    line-height: 14px;
    text-align: center;
    font-size: 0.85rem;
    font-weight: bold;
    color: #555;
    background: #e9ecef;
    border: 1px solid #ced4da;
    border-radius: 3px;
    margin-right: 2px;
    flex-shrink: 0;
  }
  details[open] > summary .tree-toggle::before {
    content: "−";
  }
  details > summary:hover {
    background: #e9ecef;
  }
</style>
"""

# 계층 구조(트리) 화면 출력
tree_html = tree_to_html(tree_data, depth=0)
st.markdown(
    TREE_CSS +
    f'<div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; '
    f'padding:16px; max-height:520px; overflow-y:auto; font-family:monospace;">'
    f'{tree_html}'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("---")


# ── 챗봇 ──────────────────────────────────────────────────────────────────────

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

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
