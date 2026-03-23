# -*- coding: utf-8 -*-

import os
import html as _html
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
    """경로를 재귀적으로 읽어 트리 구조 dict 반환."""
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


def tree_to_html(node: dict, depth: int = 0) -> str:
    """트리 dict를 <details>/<summary> 기반 HTML로 변환.
    .md/.csv 파일은 onclick 핸들러로 숨김 text_input 값을 변경 → Streamlit rerun.
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
            f'<span style="font-size:0.72rem;color:#888;margin-left:6px;">'
            f'({child_count})</span>'
        )
        return (
            f'<details {open_attr} class="tree-node"'
            f' style="margin-left:{indent_px}px; margin-top:2px;">'
            f'<summary style="cursor:pointer; padding:3px 4px; border-radius:4px;'
            f' list-style:none; display:flex; align-items:center; gap:4px;'
            f' font-size:0.88rem; user-select:none;">'
            f'<span class="tree-toggle"></span>'
            f'📁 <b>{_html.escape(node["name"])}</b>{count_badge}'
            f'</summary>'
            f'<div style="border-left:1px dashed #ccc; margin-left:12px; padding-left:4px;">'
            f'{children_html}'
            f'</div>'
            f'</details>'
        )

    # ── 파일 노드 ──
    icon = _file_icon(node["name"])
    name_escaped = _html.escape(node["name"])
    ext = pathlib.Path(node["name"]).suffix.lower()

    if ext in (".md", ".csv"):
        # onclick: React 내부 setter로 숨김 input 값 주입 → Enter keydown으로 즉시 rerun
        safe_path = node["path"].replace("\\", "\\\\").replace("'", "\\'")
        js_raw = (
            "(function(){"
            "var el=document.querySelector(\"input[aria-label='_tree_file_']\");"
            "if(!el)return;"
            "var s=Object.getOwnPropertyDescriptor("
            "window.HTMLInputElement.prototype,'value').set;"
            f"s.call(el,'{safe_path}|{ext}');"
            "el.dispatchEvent(new Event('input',{bubbles:true}));"
            "el.dispatchEvent(new KeyboardEvent("
            "'keydown',{key:'Enter',keyCode:13,bubbles:true}));"
            "})()"
        )
        # HTML 속성 안에 쓸 수 있도록 이스케이프 (& " < > → 엔티티)
        onclick_attr = _html.escape(js_raw, quote=True)
        return (
            f'<div style="margin-left:{indent_px + 20}px; padding:2px 4px;">'
            f'<span onclick="{onclick_attr}"'
            f' style="cursor:pointer; font-size:0.85rem; font-family:monospace;'
            f' color:#1a6cc4; text-decoration:underline dotted;"'
            f' title="{_html.escape(node["path"], quote=True)}">'
            f'{icon} {name_escaped}'
            f'</span>'
            f'</div>'
        )

    # 일반 파일
    return (
        f'<div style="margin-left:{indent_px + 20}px; padding:2px 4px;'
        f' font-size:0.85rem; color:#555; font-family:monospace;">'
        f'{icon} {name_escaped}'
        f'</div>'
    )


# 현재 스크립트 위치를 루트로 사용
BASE_DIR = pathlib.Path(os.path.abspath(__file__)).parent

# ── 세션 상태 초기화 ───────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_file" not in st.session_state:
    st.session_state.selected_file = None
    st.session_state.selected_file_ext = None

# ── 숨김 text_input (파일 클릭 → JS 값 주입 → Streamlit rerun 트리거) ──────────
# label을 'tree_file_'로 두면 input[aria-label='_tree_file_'] 로 쿼리 가능
_raw_file_selection = st.text_input(
    "_tree_file_",
    value="",
    key="tree_file_input",
    label_visibility="collapsed",
)

# 값이 변경되면 session_state에 저장하고 input을 초기화
if _raw_file_selection and "|" in _raw_file_selection:
    _parts = _raw_file_selection.split("|", 1)
    st.session_state.selected_file = _parts[0]
    st.session_state.selected_file_ext = _parts[1]
    st.query_params["sf"] = _parts[0]
    st.query_params["sx"] = _parts[1]
    # 다음 rerun에서 중복 처리 방지
    st.session_state["tree_file_input"] = ""

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* 숨김 text_input 전체 감춤 */
  div:has(> div > input[aria-label="_tree_file_"]) {
    display: none !important;
  }

  /* 트리 +/- 토글 배지 */
  .tree-toggle::before {
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
    margin-right: 4px;
    flex-shrink: 0;
  }
  details[open] > summary .tree-toggle::before { content: "−"; }
  details > summary:hover { background: #f1f3f5; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── 트리 출력 ──────────────────────────────────────────────────────────────────
st.markdown("#### 📂 디렉토리 구조")
st.caption(f"기준 경로: `{BASE_DIR}`")

tree_data: dict = build_tree(BASE_DIR)
tree_html = tree_to_html(tree_data, depth=0)

st.markdown(
    f'<div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px;'
    f' padding:16px; max-height:520px; overflow-y:auto; font-family:monospace;">'
    f'{tree_html}'
    f'</div>',
    unsafe_allow_html=True,
)

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
            st.query_params.clear()
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

if not API_KEY or API_KEY == "":
    st.warning("⚠️ OpenAI API 키가 설정되지 않았습니다. Streamlit secrets를 확인해주세요.")
