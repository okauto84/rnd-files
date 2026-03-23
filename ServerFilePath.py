# -*- coding: utf-8 -*-
"""
기본 시작 경로는 **이 스크립트(ServerFilePath.py)가 있는 디렉터리**입니다.
(인자로 다른 경로를 주면 그 경로부터 탐색합니다.)

모든 폴더·하위 폴더·파일을 재귀 탐색하고, 각 노드에 절대 경로(path)와
파일명·폴더명(name, 확장자 포함)을 담은 dict를 ServerFilePath.json 으로 저장합니다.

사용법:
  python ServerFilePath.py              # 시작 = 스크립트 위치 폴더
  python ServerFilePath.py /other/path  # 시작 경로 지정

참고: Jupyter/IPython 등에서 스크립트 실행 시 ``-f`` 같은 옵션이 argv에 들어오면
이전에는 이를 경로로 잘못 해석해 ``{cwd}/-f`` 를 찾는 오류가 났습니다.
``-`` 로 시작하는 인자는 무시합니다.

Jupyter 노트북에 코드를 붙여 실행하면 ``__file__`` 이 없으므로,
시작 경로·JSON 저장 위치 모두 **현재 작업 디렉터리(cwd)** 를 사용합니다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def script_directory() -> Path:
    """ServerFilePath.py 가 있는 폴더. Jupyter 등 ``__file__`` 없으면 cwd."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd().resolve()


def build_file_tree(path: Path) -> dict | None:
    """폴더·파일을 재귀적으로 dict 트리로 만든다.
    - directory: name, path, children
    - file: name, path (파일명은 확장자 포함)
    """
    path = path.resolve()
    if not path.exists():
        return None

    if path.is_file():
        return {
            "type": "file",
            "name": path.name,
            "path": str(path),
        }

    children: list[dict] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            node = build_file_tree(child)
            if node is not None:
                children.append(node)
    except PermissionError:
        pass

    display_name = path.name if path.name else str(path)
    return {
        "type": "directory",
        "name": display_name,
        "path": str(path),
        "children": children,
    }


def resolve_start_path() -> Path:
    """시작 경로 결정. ``-`` 로 시작하는 인자(Jupyter ``-f`` 등)는 무시.
    위치 인자가 없으면 **스크립트 파일이 있는 디렉터리**에서 시작."""
    pos_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if pos_args:
        return Path(pos_args[0]).expanduser().resolve()
    return script_directory()


def main() -> None:
    start = resolve_start_path()

    if not start.exists():
        print(f"오류: 경로가 존재하지 않습니다: {start}", file=sys.stderr)
        sys.exit(1)

    tree = build_file_tree(start)
    if tree is None:
        print(f"오류: 트리를 만들 수 없습니다: {start}", file=sys.stderr)
        sys.exit(1)

    out_path = script_directory() / "ServerFilePath.json"
    payload = {
        "root_path": str(start),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "tree": tree,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {out_path}")
    print(f"시작 경로: {start}")


if __name__ == "__main__":
    main()
