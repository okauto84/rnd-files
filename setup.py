# -*- coding: utf-8 -*-

import os
import json
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

# 트리에 표시하고 클릭으로 열 수 있는 확장자
VIEWABLE_EXTS: set[str] = {".md", ".csv", ".txt", ".py", ".ipynb"}


def _find_server_dir() -> pathlib.Path:
    """'Server' 폴더를 CWD → 스크립트 위치 순으로 탐색해 반환.
    1) 해당 디렉토리 직하의 'Server' 하위 폴더
    2) 경로 중 'Server' 세그먼트가 있으면 그 지점
    3) 없으면 CWD 사용
    """
    candidates = [
        pathlib.Path(os.getcwd()),
        pathlib.Path(os.path.abspath(__file__)).parent,
    ]
    for base in candidates:
        # 직접 하위에 'Server' 폴더가 있는지 확인
        sub = base / "Server"
        if sub.is_dir():
            return sub
        # 경로 세그먼트 중 'Server' 찾기 (대소문자 구분 없이)
        parts = base.parts
        for i, part in enumerate(parts):
            if part.lower() == "server":
                return pathlib.Path(*parts[: i + 1])
    return pathlib.Path(os.getcwd())


def build_tree(path: pathlib.Path) -> dict | None:
    """경로를 재귀적으로 읽어 트리 구조 dict 반환.
    파일은 VIEWABLE_EXTS에 속하는 것만 포함.
    허용 파일이 하나도 없는 폴더는 None 반환(루트 제외).
    """
    if path.is_file():
        if path.suffix.lower() not in VIEWABLE_EXTS:
            return None
        return {"name": path.name, "type": "file", "path": str(path)}

    # 디렉토리
    children: list[dict] = []
    try:
        entries = sorted(
            path.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower())
        )
        for child in entries:
            child_node = build_tree(child)
            if child_node is not None:
                children.append(child_node)
    except PermissionError:
        pass

    return {
        "name": path.name or str(path),
        "type": "dir",
        "path": str(path),
        "children": children,
    }


def _file_icon(filename: str) -> str:
    """확장자별 파일 아이콘 반환."""
    ext = pathlib.Path(filename).suffix.lower()
    icons = {
        ".py": "🐍", ".ipynb": "📓",
        ".md": "📝", ".txt": "📄", ".csv": "📊",
        ".js": "🟨", ".ts": "🔷", ".tsx": "🔷", ".jsx": "🟨",
        ".html": "🌐", ".css": "🎨", ".json": "📋", ".yaml": "📋", ".yml": "📋",
        ".xlsx": "📊", ".xls": "📊",
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

    if ext in VIEWABLE_EXTS:
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


# 'Server' 폴더를 기준 경로로 사용
BASE_DIR = _find_server_dir()

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

tree_data = build_tree(BASE_DIR)
tree_html = tree_to_html(tree_data, depth=0) if tree_data else "<p>표시할 파일이 없습니다.</p>"

st.markdown(
    f'<div style="background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px;'
    f' padding:16px; max-height:520px; overflow-y:auto; font-family:monospace;">'
    f'{tree_html}'
    f'</div>',
    unsafe_allow_html=True,
)

# 트리 구조 dict (화면 하단 출력)
st.markdown("##### 📋 트리 구조 (dict)")
if tree_data is not None:
    st.json(tree_data)
else:
    st.caption("트리 데이터가 없습니다. (허용 확장자 파일이 없거나 경로를 확인하세요.)")

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

    try:
        if ext == ".md":
            content = fp.read_text(encoding="utf-8")
            st.markdown(content)

        elif ext == ".csv":
            df = pd.read_csv(str(fp))
            st.dataframe(df, use_container_width=True)

        elif ext == ".txt":
            content = fp.read_text(encoding="utf-8")
            st.text(content)

        elif ext == ".py":
            content = fp.read_text(encoding="utf-8")
            st.code(content, language="python")

        elif ext == ".ipynb":
            nb = json.loads(fp.read_text(encoding="utf-8"))
            cells = nb.get("cells", [])
            if not cells:
                st.info("셀이 없는 노트북입니다.")
            for idx, cell in enumerate(cells):
                cell_type = cell.get("cell_type", "")
                source = "".join(cell.get("source", []))
                if not source.strip():
                    continue
                if cell_type == "markdown":
                    st.markdown(source)
                elif cell_type == "code":
                    st.code(source, language="python")
                else:
                    st.text(source)

    except Exception as e:
        st.error(f"파일을 읽을 수 없습니다: {e}")

st.markdown("---")


# ── 챗봇 ──────────────────────────────────────────────────────────────────────
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

if not API_KEY or API_KEY == "":
    st.warning("⚠️ OpenAI API 키가 설정되지 않았습니다. Streamlit secrets를 확인해주세요.")
