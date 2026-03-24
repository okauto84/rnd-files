# -*- coding: utf-8 -*-

import os
import json
import html as _html
import time
import pathlib
import streamlit as st
from openai import OpenAI


st.set_page_config(page_title="Structure", page_icon="💬", layout="wide")

try:
    API_KEY = st.secrets.get("openai_api_key", "")
except:
    API_KEY = ""

model_name = "gpt-5-mini"


# ── 디렉토리 트리 ──────────────────────────────────────────────────────────────

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
FILES_JSON_PATH = SCRIPT_DIR / "files.json"


@st.cache_data(show_spinner="files.json 로드 중…")
def _load_files_manifest(json_path_str: str, _mtime: float) -> dict:
    with open(json_path_str, encoding="utf-8") as f:
        return json.load(f)


def _is_dir_node(node: dict) -> bool:
    return node.get("type") in ("directory", "dir")


def _is_file_node(node: dict) -> bool:
    return node.get("type") in ("file",)


def apply_structure_from_tree(parent: pathlib.Path, node: dict) -> None:
    """files.json 트리 노드 기준으로 parent 아래에 폴더·빈 파일을 만든다."""
    if _is_dir_node(node):
        here = parent / node["name"]
        here.mkdir(parents=True, exist_ok=True)
        for child in node.get("children") or []:
            apply_structure_from_tree(here, child)
    elif _is_file_node(node):
        fp = parent / node["name"]
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.touch(exist_ok=True)


def build_tree(path: pathlib.Path) -> dict | None:
    """트리 dict. 모든 파일·폴더 포함. 파일 노드: name, path, type='file'."""
    if path.is_file():
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
    ext = pathlib.Path(filename).suffix.lower()
    return {
        ".md": "📝", ".csv": "📊", ".txt": "📄", ".py": "🐍", ".ipynb": "📓",
        ".json": "📋", ".yaml": "📋", ".yml": "📋",
        ".html": "🌐", ".css": "🎨", ".js": "🟨", ".ts": "🔷",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".gif": "🖼️", ".svg": "🖼️",
        ".pdf": "📕", ".zip": "📦", ".xml": "📋",
    }.get(ext, "📄")


def tree_to_html(node: dict, depth: int = 0) -> str:
    """트리 HTML. 파일은 파일명만 표시(클릭·선택 없음)."""
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

    name_esc = _html.escape(node["name"])
    icon = _file_icon(node["name"])
    return (
        f'<div style="margin-left:{indent_px + 20}px;padding:2px 4px;'
        f'font-size:0.85rem;font-family:monospace;color:#555;">'
        f'{icon} {name_esc}</div>'
    )


def build_qa_system_prompt(base_dir: pathlib.Path, tree_dict: dict | None) -> str:
    """OpenAPI 질의응답용 시스템 프롬프트. 디렉터리 트리(JSON)를 근거로 답하도록 지시."""
    tree_json = json.dumps(tree_dict, ensure_ascii=False, indent=2) if tree_dict else "{}"
    return f"""당신은 아래에 주어진 **디렉터리 트리 정보**만을 근거로 사용자의 질문에 답하는 도우미입니다.

## 기준 루트 경로
`{base_dir}`

이 트리에는 기준 경로 아래에서 읽을 수 있는 **모든 파일과 폴더**가 포함됩니다(확장자 제한 없음).

## 디렉터리 트리 (JSON)
각 노드의 의미:
- `type`: `"dir"` 이면 폴더, `"file"` 이면 파일
- `name`: 표시 이름(파일명 또는 폴더명)
- `path`: 절대 경로
- `children`: 폴더일 때만, 하위 노드 배열

```json
{tree_json}
```

## 답변 규칙
1. 질문에 답할 때 **위 JSON에 실제로 존재하는 폴더·파일·경로**만 인용하세요.
2. 구조 요약, 특정 확장자 목록, 경로 찾기, 상대 위치, 폴더별 파일 개수 등은 트리를 직접 근거로 설명하세요.
3. 트리가 비어 있거나 질문과 무관하면, 그 사실을 짧게 밝히고 일반적인 안내만 하세요.
4. **한국어**로 답변하세요.
"""


# ── 앱 본문 ────────────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("#### 📂 디렉토리 구조")

if not FILES_JSON_PATH.is_file():
    st.error(f"`files.json`을 찾을 수 없습니다: `{FILES_JSON_PATH}`")
    st.stop()

_mtime = FILES_JSON_PATH.stat().st_mtime
manifest = _load_files_manifest(str(FILES_JSON_PATH), _mtime)
tree_root = manifest.get("tree")
if not tree_root or not _is_dir_node(tree_root):
    st.error("`files.json`에 유효한 루트 `tree`(directory)가 없습니다.")
    st.stop()

BASE_DIR = SCRIPT_DIR / tree_root["name"]
_apply_key = f"{FILES_JSON_PATH.resolve()}|{_mtime}"
if st.session_state.get("_files_json_applied_key") != _apply_key:
    apply_structure_from_tree(SCRIPT_DIR, tree_root)
    st.session_state._files_json_applied_key = _apply_key

st.caption(
    f"정의 파일: `{FILES_JSON_PATH}` · 기준 경로: `{BASE_DIR}`"
    + (f" · 원본 루트: `{manifest.get('root_path', '')}`" if manifest.get("root_path") else "")
)

tree_data = build_tree(BASE_DIR)
_tree_html = tree_to_html(tree_data) if tree_data else "<p>표시할 파일이 없습니다.</p>"

# 스타일은 짧은 마크다운으로만 주입. 트리 본문은 st.html로 넣어(가능 시) 마크다운 파서가 긴 HTML을 끊지 않게 함.
# Streamlit 세로 flex(min-height:0 등) 때문에 패널 배경만 잘리는 경우 → :has(.tree-panel-wrap) 상위에 overflow/높이 완화.
_TREE_PANEL_STYLES = """
<style>
  [data-testid="stVerticalBlockBorderWrapper"]:has(.tree-panel-wrap),
  [data-testid="stVerticalBlock"]:has(.tree-panel-wrap),
  [data-testid="stElementContainer"]:has(.tree-panel-wrap),
  [data-testid="stMarkdownContainer"]:has(.tree-panel-wrap),
  [data-testid="stHtmlContainer"]:has(.tree-panel-wrap) {
    overflow: visible !important;
    max-height: none !important;
    height: auto !important;
  }
  [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.tree-panel-wrap) {
    flex: 0 0 auto !important;
    min-height: fit-content !important;
  }
  .tree-panel-wrap {
    font-family: monospace;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
    display: flow-root;
    overflow: visible;
    min-height: min-content;
  }
  .tree-panel-wrap .tree-toggle::before {
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
  .tree-panel-wrap details[open] > summary .tree-toggle::before { content: "−"; }
  .tree-panel-wrap details > summary {
    cursor: pointer;
    padding: 3px 4px;
    border-radius: 4px;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.88rem;
    user-select: none;
  }
  .tree-panel-wrap details > summary:hover { background: #f1f3f5; }
</style>
"""

st.markdown(_TREE_PANEL_STYLES, unsafe_allow_html=True)

_tree_panel_body = f'<div class="tree-panel-wrap">{_tree_html}</div>'
if hasattr(st, "html"):
    st.html(_tree_panel_body)
else:
    st.markdown(_tree_panel_body, unsafe_allow_html=True)

st.markdown("---")

st.markdown("#### 💬 Q&A")


def call_openai_api(messages: list) -> str:
    try:
        if not API_KEY:
            return "⚠️ API 키가 설정되지 않았습니다. Streamlit secrets의 openai_api_key를 설정해주세요."
        client = OpenAI(api_key=API_KEY)
        resp = client.chat.completions.create(model=model_name, messages=messages)
        return (resp.choices[0].message.content or "").strip()
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
        system_prompt = build_qa_system_prompt(BASE_DIR, tree_data)
        messages_for_api = [
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        ]
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
