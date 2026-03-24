"""
현재 작업 디렉터리(또는 인자로 준 루트) 아래의 모든 디렉터리 경로만 수집하여 JSON으로 저장합니다.
파일은 기록하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def should_skip_dir(name: str, skip_hidden: bool) -> bool:
    if name == ".git":
        return True
    if skip_hidden and name.startswith("."):
        return True
    return False


def collect_directories(root: Path, skip_hidden: bool) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"루트가 디렉터리가 아닙니다: {root}")

    all_dirs: list[Path] = [root]

    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, skip_hidden)]
        current = Path(dirpath).resolve()
        for name in dirnames:
            all_dirs.append((current / name).resolve())

    unique = sorted(set(all_dirs), key=lambda p: str(p).lower())
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="하위 폴더 경로만 수집하여 JSON 저장")
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="탐색 루트 경로 (기본: 현재 작업 디렉터리)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="directories.json",
        help="저장할 JSON 파일 경로 (기본: directories.json)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="이름이 . 로 시작하는 디렉터리도 포함 (.git 제외)",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    directories = collect_directories(root, skip_hidden=not args.include_hidden)

    payload = {
        "root_path": str(root.resolve()),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "directories": [str(p) for p in directories],
    }

    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON 저장: {out_path.resolve()}")
    print(f"디렉터리 수: {len(directories)}")


if __name__ == "__main__":
    main()
