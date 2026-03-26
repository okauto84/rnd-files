"""
현재 작업 디렉터리(또는 인자로 준 루트) 아래의 모든 디렉터리 경로만 수집하여 JSON으로 저장합니다.
.git 및 .ipynb_checkpoints 폴더는 항상 제외합니다.
실제 파일 목록은 스캔하지 않으며, 최하위(리프) 디렉터리에는 readme.md가 하나 있다고 가정해 해당 경로만 JSON에 포함합니다.
기본 출력 파일은 filepath.json 입니다.
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
    if name == ".ipynb_checkpoints":
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


def path_relative_to_cwd(p: Path, cwd: Path) -> str:
    try:
        rel = p.resolve().relative_to(cwd.resolve())
    except ValueError:
        rel = p.resolve()
    return rel.as_posix()


def is_leaf_directory(dir_path: Path, all_dirs: set[Path]) -> bool:
    for other in all_dirs:
        if other == dir_path:
            continue
        try:
            other.relative_to(dir_path)
            return False
        except ValueError:
            continue
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="하위 폴더 경로만 수집하여 JSON 저장 (리프에 readme.md 경로 포함)")
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="탐색 루트 경로 (기본: 현재 작업 디렉터리)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="filepath.json",
        help="저장할 JSON 파일 경로 (기본: filepath.json)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="이름이 . 로 시작하는 디렉터리도 포함 (.git 제외)",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    root = Path(args.root).expanduser()
    directories = collect_directories(root, skip_hidden=not args.include_hidden)
    dir_set = set(directories)

    dir_rel = [path_relative_to_cwd(p, cwd) for p in directories]

    readme_entries: list[dict[str, str]] = []
    for p in directories:
        if not is_leaf_directory(p, dir_set):
            continue
        d_rel = path_relative_to_cwd(p, cwd)
        readme_rel = f"{d_rel.rstrip('/')}/readme.md"
        readme_entries.append({"directory": d_rel, "readme_md": readme_rel})

    payload = {
        "cwd": str(cwd.resolve()),
        "root_path": str(root.resolve()),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "directories": dir_rel,
        "readme_md_by_leaf": readme_entries,
    }

    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON 저장: {out_path.resolve()}")
    print(f"디렉터리 수: {len(directories)}")
    print(f"리프 디렉터리(가정 readme.md) 수: {len(readme_entries)}")


if __name__ == "__main__":
    main()
