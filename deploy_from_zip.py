"""Render build step: use the newest timestamped God8 release ZIP in this repo.

Keep this file and render.yaml outside the archive. The archive is uploaded to
GitHub intact; Render extracts the app code only during each service build.
"""
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
PATTERN = re.compile(r"god8_release_[0-9]{12}\.zip\Z")
REQUIRED = {"core.py", "web.py", "collector_service.py", "worker_ai.py",
            "requirements.txt", "templates/base.html", "static/app.js"}
PROTECTED = {"render.yaml", "deploy_from_zip.py"}


def entries(archive):
    selected = {}
    for info in archive.infolist():
        name = info.filename
        if "\\" in name or name.startswith("/"):
            raise ValueError(f"unsafe ZIP path: {name}")
        parts = [part for part in PurePosixPath(name).parts if part != "."]
        if not parts or ".." in parts:
            raise ValueError(f"unsafe ZIP path: {name}")
        rel = PurePosixPath(*parts)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError(f"ZIP link is not allowed: {name}")
        if info.is_dir():
            continue
        key = str(rel)
        if key in selected:
            raise ValueError(f"duplicate ZIP path: {key}")
        selected[key] = info
    missing = REQUIRED.difference(selected)
    if missing:
        raise ValueError(f"release ZIP missing required files: {', '.join(sorted(missing))}")
    return selected


def deploy(root=ROOT):
    archives = sorted(p for p in root.iterdir() if PATTERN.fullmatch(p.name))
    if not archives:
        raise FileNotFoundError("upload god8_release_YYYYMMDDHHMM.zip to repository root")
    selected_archive = archives[-1]
    with zipfile.ZipFile(selected_archive) as archive:
        selected = entries(archive)
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt ZIP member: {bad}")
        with tempfile.TemporaryDirectory(prefix="god8-build-") as temp:
            staging = Path(temp)
            for rel, info in selected.items():
                if rel in PROTECTED or rel.startswith((".git/", ".github/")):
                    continue
                target = staging.joinpath(*PurePosixPath(rel).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
            for file in staging.rglob("*"):
                if file.is_file():
                    dest = root / file.relative_to(staging)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, dest)
    print(f"God8 release extracted: {selected_archive.name} ({len(selected)} files)")
    return selected_archive.name


if __name__ == "__main__":
    deploy()
