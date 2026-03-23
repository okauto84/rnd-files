# -*- coding: utf-8 -*-

import os
import json
import html as _html
import time
import pathlib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI


st.set_page_config(page_title="Structure", page_icon="💬", layout="wide")

try:
    API_KEY = st.secrets.get("openai_api_key", "")
except:
    API_KEY = ""

model_name = "gpt-5.4"


# ── 디렉토리 트리 ──────────────────────────────────────────────────────────────

VIEWABLE_EXTS: set[str] = {".md", ".csv", ".txt", ".py", ".ipynb"}


def _find_server_dir() -> pathlib.Path:
    """'Server' 폴더를 CWD → 스크립트 위치 순으로 탐색."""
    for base in (pathlib.Path(os.getcwd()), pathlib.Path(os.path.abspath(__file__)).parent):
        sub = base / "Server"
        if sub.is_dir():
            return sub
        for i, part in enumerate(base.parts):
            if part.lower() == "server":
                return pathlib.Path(*base.parts[: i + 1])
    return pathlib.Path(os.getcwd())


def build_tree(path: pathlib.Path) -> dict | None:
    """트리 dict. 파일 노드: name(파일명), path(절대경로), type='file'.
    허용 확장자만 포함."""
    if path.is_file():
        if path.suffix.lower() not in VIEWABLE_EXTS:
            return None
        return {
            "type": "file",
            "name": path.name,
            "path": str(path.resolve()),
        }

    children: list[dict] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            node = build_tree(child)
            if node is not None:
                children.append(node)
    except PermissionError:
        pass

    return {
        "name": path.name or str(path),
        "type": "dir",
        "path": str(path.resolve()),
        "children": children,
    }


def _file_icon(filename: str) -> str:
    return {
        ".md": "📝", ".csv": "📊", ".txt": "📄", ".py": "🐍", ".ipynb": "📓",
    }.get(pathlib.Path(filename).suffix.lower(), "📄")


def tree_to_html(node: dict, depth: int = 0) -> str:
    """트리 HTML. 파일은 화면에 파일명(name)만 표시, 클릭 시 path로 선택."""
    indent_px = depth * 20

    if node["type"] == "dir":
        children_html = "".join(tree_to_html(c, depth + 1) for c in node.get("children", []))
        open_attr = "open" if depth == 0 else ""
        n = len(node.get("children", []))
        badge = f'<span style="font-size:0.72rem;color:#888;margin-left:6px;">({n})</span>'
        return (
            f'<details {open_attr} style="margin-left:{indent_px}px;margin-top:2px;">'
            f'<summary style="cursor:pointer;padding:3px 4px;border-radius:4px;'
            f'list-style:none;display:flex;align-items:center;gap:4px;'
            f'font-size:0.88rem;user-select:none;">'
            f'<span class="tree-toggle"></span>📁 <b>{_html.escape(node["name"])}</b>{badge}'
            f'</summary>'
            f'<div style="border-left:1px dashed #ccc;margin-left:12px;padding-left:4px;">'
            f'{children_html}</div></details>'
        )

    # 파일: 표시는 name만 (경로는 DOM에 노출하지 않음)
    name_esc = _html.escape(node["name"])
    ext = pathlib.Path(node["name"]).suffix.lower()
    icon = _file_icon(node["name"])
    safe_path = node["path"].replace("\\", "\\\\").replace("'", "\\'")
    onclick = _html.escape(f"selectFile('{safe_path}','{ext}')", quote=True)
    return (
        f'<div style="margin-left:{indent_px + 20}px;padding:2px 4px;">'
        f'<span onclick="{onclick}"'
        f' style="cursor:pointer;font-size:0.85rem;font-family:monospace;'
        f'color:#1a6cc4;text-decoration:underline dotted;">'
        f'{icon} {name_esc}</span></div>'
    )


def _resolve_safe_file(base_dir: pathlib.Path, path_str: str, ext: str) -> pathlib.Path | None:
    """BASE_DIR 밖·허용 확장자 외 접근 차단."""
    ext = (ext or "").lower().strip()
    if ext not in VIEWABLE_EXTS:
        return None
    try:
        p = pathlib.Path(path_str).resolve()
        if p.suffix.lower() not in VIEWABLE_EXTS:
            return None
        p.relative_to(base_dir.resolve())
        return p
    except (ValueError, OSError):
        return None


# ── 앱 본문 ────────────────────────────────────────────────────────────────────

BASE_DIR = _find_server_dir()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_file" not in st.session_state:
    st.session_state.selected_file = None
    st.session_state.selected_file_ext = None

# query_params 복원
_qsf, _qsx = st.query_params.get("sf", ""), st.query_params.get("sx", "")
if _qsf and _qsx:
    _safe = _resolve_safe_file(BASE_DIR, _qsf, _qsx)
    if _safe is not None:
        st.session_state.selected_file = str(_safe)
        st.session_state.selected_file_ext = _safe.suffix.lower()

_raw = st.text_input(
    label="_tree_file_",
    value="",
    key="tree_file_input",
    placeholder="__tree_file__",
    label_visibility="collapsed",
)
if _raw and "|" in _raw:
    _p, _x = _raw.split("|", 1)
    _safe = _resolve_safe_file(BASE_DIR, _p, _x)
    if _safe is not None:
        st.session_state.selected_file = str(_safe)
        st.session_state.selected_file_ext = _safe.suffix.lower()
        st.query_params["sf"] = str(_safe)
        st.query_params["sx"] = _safe.suffix.lower()
    st.session_state["tree_file_input"] = ""

st.markdown(
    "<style>div:has(input[placeholder='__tree_file__']){display:none!important}</style>",
    unsafe_allow_html=True,
)

st.markdown("#### 📂 디렉토리 구조")
st.caption(f"기준 경로: `{BASE_DIR}`")

tree_data = build_tree(BASE_DIR)
_tree_html = tree_to_html(tree_data) if tree_data else "<p>표시할 파일이 없습니다.</p>"

components.html(
    "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
    "html,body{margin:0;padding:0}"
    "body{padding:12px;font-family:monospace;background:#f8f9fa;"
    "border:1px solid #dee2e6;border-radius:8px}"
    ".tree-toggle::before{content:'+';display:inline-flex;align-items:center;"
    "justify-content:center;width:16px;height:16px;font-size:.82rem;font-weight:bold;"
    "color:#555;background:#e9ecef;border:1px solid #ced4da;border-radius:3px;"
    "margin-right:4px;flex-shrink:0}"
    "details[open]>summary .tree-toggle::before{content:'−'}"
    "details>summary{cursor:pointer;padding:3px 4px;border-radius:4px;"
    "list-style:none;display:flex;align-items:center;gap:4px;"
    "font-size:.88rem;user-select:none}"
    "details>summary:hover{background:#f1f3f5}"
    "</style></head><body>"
    + _tree_html
    + "<script>"
    "function selectFile(path,ext){"
    "try{"
    "var doc=window.parent.document;"
    "var el=doc.querySelector(\"input[placeholder='__tree_file__']\");"
    "if(el){"
    "var s=Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype,'value').set;"
    "s.call(el,path+'|'+ext);"
    "el.dispatchEvent(new window.parent.Event('input',{bubbles:true}));"
    "el.dispatchEvent(new window.parent.Event('change',{bubbles:true}));"
    "el.focus();"
    "el.dispatchEvent(new window.parent.KeyboardEvent('keydown',"
    "{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));"
    "return;}"
    "window.parent.location.href=window.parent.location.pathname"
    "+'?sf='+encodeURIComponent(path)+'&sx='+encodeURIComponent(ext);"
    "}catch(e){"
    "try{window.parent.location.href=window.parent.location.pathname"
    "+'?sf='+encodeURIComponent(path)+'&sx='+encodeURIComponent(ext);}catch(e2){}}}"
    "</script></body></html>",
    height=500,
    scrolling=True,
)

st.markdown("##### 📋 트리 구조 (dict)")
if tree_data is not None:
    st.json(tree_data)
else:
    st.caption("트리 데이터가 없습니다.")

# ── 선택 파일: path로 읽기, 화면에는 파일명 위주 ───────────────────────────────
if st.session_state.selected_file:
    fp = pathlib.Path(st.session_state.selected_file)
    ext = (st.session_state.selected_file_ext or "").lower()

    st.markdown("---")
    col_title, col_close = st.columns([11, 1])
    with col_title:
        st.markdown(f"##### 📄 {fp.name}")
    with col_close:
        if st.button("✕ 닫기", key="close_preview"):
            st.session_state.selected_file = None
            st.session_state.selected_file_ext = None
            st.query_params.clear()
            st.rerun()

    _verified = _resolve_safe_file(BASE_DIR, str(fp), ext)
    if _verified is None:
        st.error("허용되지 않은 파일이거나 기준 경로 밖의 경로입니다.")
    else:
        try:
            if ext == ".md":
                st.markdown(_verified.read_text(encoding="utf-8"))
            elif ext == ".csv":
                st.dataframe(pd.read_csv(str(_verified)), use_container_width=True)
            elif ext == ".txt":
                st.text(_verified.read_text(encoding="utf-8"))
            elif ext == ".py":
                st.code(_verified.read_text(encoding="utf-8"), language="python")
            elif ext == ".ipynb":
                nb = json.loads(_verified.read_text(encoding="utf-8"))
                cells = nb.get("cells", [])
                if not cells:
                    st.info("셀이 없는 노트북입니다.")
                for cell in cells:
                    src = "".join(cell.get("source", []))
                    if not src.strip():
                        continue
                    ct = cell.get("cell_type", "")
                    if ct == "markdown":
                        st.markdown(src)
                    elif ct == "code":
                        st.code(src, language="python")
                    else:
                        st.text(src)
        except Exception as e:
            st.error(f"파일을 읽을 수 없습니다: {e}")

st.markdown("---")

st.markdown("#### 💬 Q&A")


def call_openai_api(messages: list) -> str:
    try:
        if not API_KEY:
            return "⚠️ API 키가 설정되지 않았습니다. Streamlit secrets의 openai_api_key를 설정해주세요."
        client = OpenAI(api_key=API_KEY)
        return client.chat.completions.create(model=model_name, messages=messages).choices[0].message.content
    except Exception as e:
        err = str(e)
        if "authentication" in err.lower() or "invalid" in err.lower():
            return f"🔑 API 키 오류: {err}"
        if "quota" in err.lower() or "limit" in err.lower() or "rate" in err.lower():
            return f"📊 사용량 한도 초과: {err}"
        return f"❌ 오류: {err}"


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("질문해보세요!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        messages_for_api = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        with st.spinner("생성AI가 답변을 생성하고 있습니다..."):
            response = call_openai_api(messages_for_api)
        placeholder = st.empty()
        displayed = ""
        for char in response:
            displayed += char
            placeholder.markdown(displayed + "▌")
            time.sleep(0.01)
        placeholder.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

if not API_KEY:
    st.warning("⚠️ OpenAI API 키가 설정되지 않았습니다. Streamlit secrets를 확인해주세요.")
