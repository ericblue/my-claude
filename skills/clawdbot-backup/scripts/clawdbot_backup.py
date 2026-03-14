#!/usr/bin/env python3
"""Clawdbot backup helper.

Creates timestamped snapshots of key Clawdbot files:
- ~/.clawdbot/clawdbot.json
- /Users/ericblue/clawd (workspace)

Backups land in /Users/ericblue/clawdbot-backup by default.

Subcommands:
- create: create snapshot folder + zip, with notes/diff vs last backup when possible
- list: list known backups
- diff: show change summary vs previous backup (no new backup)

This is intentionally conservative: it excludes heavy/churny dirs by default.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import difflib
import fnmatch
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap
import zipfile

BACKUP_ROOT_DEFAULT = pathlib.Path("/Users/ericblue/clawdbot-backup")
WORKSPACE_DEFAULT = pathlib.Path("/Users/ericblue/clawd")
CONFIG_DEFAULT = pathlib.Path(os.path.expanduser("~/.clawdbot/clawdbot.json"))

DEFAULT_EXCLUDES = [
    ".git",
    "node_modules",
    "dist",
    ".next",
    "tmp",
    "backups",
]
DEFAULT_EXCLUDE_GLOBS = [
    ".DS_Store",
    "*.log",
]

MANIFEST_VERSION = 1


@dataclasses.dataclass
class BackupPaths:
    backup_root: pathlib.Path
    workspace: pathlib.Path
    config: pathlib.Path


def _now_stamp() -> str:
    # local time, sortable
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str], cwd: pathlib.Path | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def _is_git_repo(path: pathlib.Path) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    return code == 0


def _git_info(workspace: pathlib.Path) -> dict:
    if not _is_git_repo(workspace):
        return {"isRepo": False}

    info: dict = {"isRepo": True}
    code, out, _ = _run(["git", "rev-parse", "HEAD"], cwd=workspace)
    if code == 0:
        info["head"] = out.strip()

    code, out, _ = _run(["git", "status", "--porcelain=v1"], cwd=workspace)
    if code == 0:
        info["statusPorcelain"] = out
        info["isClean"] = (out.strip() == "")

    code, out, _ = _run(["git", "diff", "--stat"], cwd=workspace)
    if code == 0:
        info["diffStat"] = out

    return info


def _should_exclude_dir(name: str, excludes: list[str]) -> bool:
    return name in excludes


def _should_exclude_file(name: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, g) for g in globs)


def _copy_tree_filtered(src: pathlib.Path, dst: pathlib.Path, excludes: list[str], file_globs: list[str]) -> None:
    """Copy src directory tree to dst excluding specified top-level dir names at any level.

    Exclusion applies to directory basenames.
    """
    src = src.resolve()
    dst = dst.resolve()

    for root, dirs, files in os.walk(src):
        root_p = pathlib.Path(root)

        # mutate dirs in-place to prune traversal
        pruned = []
        for d in list(dirs):
            if _should_exclude_dir(d, excludes):
                pruned.append(d)
                dirs.remove(d)
        
        rel_root = root_p.relative_to(src)
        out_root = dst / rel_root
        out_root.mkdir(parents=True, exist_ok=True)

        # copy files
        for f in files:
            if _should_exclude_file(f, file_globs):
                continue
            src_f = root_p / f
            # extra guard: avoid copying huge socket/special files
            try:
                st = src_f.lstat()
            except FileNotFoundError:
                continue
            if not pathlib.Path(src_f).is_file() or st.st_size < 0:
                continue
            shutil.copy2(src_f, out_root / f)


def _zip_dir(src_dir: pathlib.Path, zip_path: pathlib.Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(src_dir):
            root_p = pathlib.Path(root)
            for f in files:
                fp = root_p / f
                arcname = fp.relative_to(src_dir)
                z.write(fp, arcname.as_posix())


def _find_backups(backup_root: pathlib.Path) -> list[dict]:
    if not backup_root.exists():
        return []

    items: list[dict] = []
    for p in sorted(backup_root.glob("backup-*/")):
        manifest = p / "manifest.json"
        zipf = backup_root / (p.name + ".zip")
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        items.append(
            {
                "name": p.name,
                "dir": str(p),
                "created": dt.datetime.fromtimestamp(st.st_mtime).isoformat(),
                "hasManifest": manifest.exists(),
                "zip": str(zipf) if zipf.exists() else None,
                "zipFileUrl": f"file://{zipf}" if zipf.exists() else None,
            }
        )

    # Also include stray zip-only backups
    known_dirs = {i["name"] for i in items}
    for z in sorted(backup_root.glob("backup-*.zip")):
        base = z.name[:-4]
        if base in known_dirs:
            continue
        st = z.stat()
        items.append(
            {
                "name": base,
                "dir": None,
                "created": dt.datetime.fromtimestamp(st.st_mtime).isoformat(),
                "hasManifest": False,
                "zip": str(z),
                "zipFileUrl": f"file://{z}",
            }
        )

    # newest first
    items.sort(key=lambda x: x["created"], reverse=True)
    return items


def _load_manifest(backup_dir: pathlib.Path) -> dict | None:
    p = backup_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _collect_manifest(snapshot_dir: pathlib.Path, paths: BackupPaths, excludes: list[str], file_globs: list[str]) -> dict:
    # Inventory snapshot files relative to snapshot_dir
    files: list[dict] = []
    for root, dirs, filenames in os.walk(snapshot_dir):
        # skip excluded dirs based on basename
        dirs[:] = [d for d in dirs if d not in excludes]

        root_p = pathlib.Path(root)
        for f in filenames:
            if _should_exclude_file(f, file_globs):
                continue
            fp = root_p / f
            try:
                st = fp.stat()
            except FileNotFoundError:
                continue
            if not fp.is_file():
                continue
            rel = fp.relative_to(snapshot_dir).as_posix()
            rec = {
                "path": rel,
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            }
            # Hash small-ish files only to keep runtime bounded
            if st.st_size <= 2 * 1024 * 1024:
                rec["sha256"] = _sha256(fp)
            files.append(rec)

    files.sort(key=lambda x: x["path"])

    return {
        "version": MANIFEST_VERSION,
        "created": dt.datetime.now().isoformat(),
        "source": {
            "config": str(paths.config),
            "workspace": str(paths.workspace),
        },
        "excludes": excludes,
        "excludeGlobs": file_globs,
        "git": _git_info(paths.workspace),
        "files": files,
    }


def _summarize_manifest_changes(prev: dict, cur: dict, max_items: int = 50) -> str:
    prev_map = {f["path"]: f for f in prev.get("files", [])}
    cur_map = {f["path"]: f for f in cur.get("files", [])}

    added = sorted(set(cur_map) - set(prev_map))
    removed = sorted(set(prev_map) - set(cur_map))

    modified = []
    for p in sorted(set(cur_map) & set(prev_map)):
        a = prev_map[p]
        b = cur_map[p]
        if a.get("sha256") and b.get("sha256"):
            if a.get("sha256") != b.get("sha256"):
                modified.append(p)
        else:
            # fallback: size/mtime heuristic
            if a.get("size") != b.get("size") or a.get("mtime") != b.get("mtime"):
                modified.append(p)

    lines = []
    lines.append(f"File inventory changes (manifest-based):")
    lines.append(f"- added: {len(added)}")
    lines.append(f"- removed: {len(removed)}")
    lines.append(f"- modified: {len(modified)}")

    def _chunk(title: str, arr: list[str]):
        if not arr:
            return
        lines.append("")
        lines.append(f"{title} (showing up to {max_items}):")
        for p in arr[:max_items]:
            lines.append(f"- {p}")
        if len(arr) > max_items:
            lines.append(f"- ... ({len(arr) - max_items} more)")

    _chunk("Added", added)
    _chunk("Removed", removed)
    _chunk("Modified", modified)

    return "\n".join(lines).strip() + "\n"


def _read_text_if_exists(p: pathlib.Path, max_bytes: int = 512 * 1024) -> str | None:
    try:
        if not p.exists() or not p.is_file():
            return None
        b = p.read_bytes()
        if len(b) > max_bytes:
            return None
        return b.decode("utf-8", errors="replace")
    except Exception:
        return None


def _unified_diff(a: str, b: str, fromfile: str, tofile: str, max_lines: int = 400) -> str:
    diff = list(
        difflib.unified_diff(
            a.splitlines(True),
            b.splitlines(True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )
    if not diff:
        return ""
    if len(diff) > max_lines:
        head = diff[:max_lines]
        head.append(f"... diff truncated ({len(diff) - max_lines} more lines)\n")
        diff = head
    return "".join(diff)


def _latest_backup_dir(backup_root: pathlib.Path) -> pathlib.Path | None:
    dirs = sorted(backup_root.glob("backup-*/"))
    if not dirs:
        return None
    # dirs are lexicographically timestamped; newest is last
    return dirs[-1]


def cmd_list(args: argparse.Namespace) -> int:
    backup_root = pathlib.Path(args.backup_root)
    items = _find_backups(backup_root)

    if args.json:
        print(json.dumps(items, indent=2))
        return 0

    if not items:
        print(f"No backups found in {backup_root}")
        return 0

    for i in items:
        print(f"- {i['name']}  created={i['created']}")
        if i.get("dir"):
            print(f"  dir: {i['dir']}")
        if i.get("zip"):
            print(f"  zip: {i['zip']}")
            print(f"  url: {i['zipFileUrl']}")
    return 0


def _build_notes(prev_dir: pathlib.Path | None, cur_manifest: dict, cur_snapshot_dir: pathlib.Path) -> str:
    parts: list[str] = []

    parts.append(f"# Clawdbot backup notes\n")
    parts.append(f"Created: {cur_manifest.get('created')}\n")
    parts.append("## Sources\n")
    parts.append(f"- config: {cur_manifest['source'].get('config')}\n")
    parts.append(f"- workspace: {cur_manifest['source'].get('workspace')}\n")

    git = cur_manifest.get("git", {})
    parts.append("\n## Git (workspace)\n")
    if not git.get("isRepo"):
        parts.append("Workspace is not a git repo (or git not available).\n")
    else:
        parts.append(f"- HEAD: {git.get('head','(unknown)')}\n")
        parts.append(f"- clean: {git.get('isClean')}\n")
        if git.get("statusPorcelain"):
            sp = git["statusPorcelain"].strip("\n")
            parts.append("\n### git status --porcelain\n\n```")
            parts.append(sp if sp else "(clean)")
            parts.append("```\n")
        if git.get("diffStat"):
            ds = git["diffStat"].strip("\n")
            parts.append("\n### git diff --stat\n\n```")
            parts.append(ds if ds else "(no unstaged diff)")
            parts.append("```\n")

    if not prev_dir:
        parts.append("\n## Changes since previous backup\n")
        parts.append("No previous backup found.\n")
        return "\n".join(parts).strip() + "\n"

    prev_manifest = _load_manifest(prev_dir)
    if prev_manifest:
        parts.append("\n## Changes since previous backup\n")
        parts.append(f"Previous: {prev_dir.name}\n")
        parts.append("\n" + _summarize_manifest_changes(prev_manifest, cur_manifest))
    else:
        parts.append("\n## Changes since previous backup\n")
        parts.append(f"Previous: {prev_dir.name} (manifest missing/unreadable)\n")

    # Config diff if possible (text)
    prev_cfg = prev_dir / "config" / "clawdbot.json"
    cur_cfg = cur_snapshot_dir / "config" / "clawdbot.json"

    a = _read_text_if_exists(prev_cfg)
    b = _read_text_if_exists(cur_cfg)
    if a is not None and b is not None:
        d = _unified_diff(a, b, str(prev_cfg), str(cur_cfg))
        if d:
            parts.append("\n## Config diff (unified)\n\n```")
            parts.append(d.rstrip("\n"))
            parts.append("```\n")

    return "\n".join(parts).strip() + "\n"


def cmd_diff(args: argparse.Namespace) -> int:
    paths = BackupPaths(
        backup_root=pathlib.Path(args.backup_root),
        workspace=pathlib.Path(args.workspace),
        config=pathlib.Path(args.config),
    )

    prev_dir = _latest_backup_dir(paths.backup_root)
    if not prev_dir:
        print(f"No previous backup found in {paths.backup_root}")
        return 0

    # Build a temp snapshot in a temp dir for diffing
    tmp = paths.backup_root / ("tmp-diff-" + _now_stamp())
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        snap = tmp / "snapshot"
        (snap / "config").mkdir(parents=True, exist_ok=True)
        if paths.config.exists():
            shutil.copy2(paths.config, snap / "config" / "clawdbot.json")

        (snap / "workspace").mkdir(parents=True, exist_ok=True)
        _copy_tree_filtered(paths.workspace, snap / "workspace", DEFAULT_EXCLUDES, DEFAULT_EXCLUDE_GLOBS)

        cur_manifest = _collect_manifest(snap, paths, DEFAULT_EXCLUDES, DEFAULT_EXCLUDE_GLOBS)
        notes = _build_notes(prev_dir, cur_manifest, snap)
        print(notes)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_create(args: argparse.Namespace) -> int:
    paths = BackupPaths(
        backup_root=pathlib.Path(args.backup_root),
        workspace=pathlib.Path(args.workspace),
        config=pathlib.Path(args.config),
    )

    stamp = _now_stamp()
    backup_name = f"backup-{stamp}"
    backup_dir = paths.backup_root / backup_name

    paths.backup_root.mkdir(parents=True, exist_ok=True)

    if backup_dir.exists():
        print(f"Backup dir already exists: {backup_dir}", file=sys.stderr)
        return 2

    prev_dir = _latest_backup_dir(paths.backup_root)

    # Create snapshot folder
    (backup_dir / "config").mkdir(parents=True, exist_ok=True)
    (backup_dir / "workspace").mkdir(parents=True, exist_ok=True)

    if paths.config.exists():
        shutil.copy2(paths.config, backup_dir / "config" / "clawdbot.json")
    else:
        (backup_dir / "config" / "MISSING_CONFIG.txt").write_text(
            f"Expected config at {paths.config} but it was not found.\n", encoding="utf-8"
        )

    if paths.workspace.exists():
        _copy_tree_filtered(paths.workspace, backup_dir / "workspace", DEFAULT_EXCLUDES, DEFAULT_EXCLUDE_GLOBS)
    else:
        (backup_dir / "workspace" / "MISSING_WORKSPACE.txt").write_text(
            f"Expected workspace at {paths.workspace} but it was not found.\n", encoding="utf-8"
        )

    # Manifest + notes
    manifest = _collect_manifest(backup_dir, paths, DEFAULT_EXCLUDES, DEFAULT_EXCLUDE_GLOBS)
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    notes = _build_notes(prev_dir, manifest, backup_dir)
    (backup_dir / "notes.md").write_text(notes, encoding="utf-8")

    # Zip
    zip_path = paths.backup_root / f"{backup_name}.zip"
    _zip_dir(backup_dir, zip_path)

    print(f"Backup created: {backup_dir}")
    print(f"Zip created: {zip_path}")
    print(f"Download URL (local): file://{zip_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clawdbot_backup.py")
    p.add_argument("--backup-root", default=str(BACKUP_ROOT_DEFAULT))
    p.add_argument("--workspace", default=str(WORKSPACE_DEFAULT))
    p.add_argument("--config", default=str(CONFIG_DEFAULT))

    sub = p.add_subparsers(dest="cmd", required=True)

    s_create = sub.add_parser("create", help="Create a new backup snapshot + zip")
    s_create.set_defaults(func=cmd_create)

    s_list = sub.add_parser("list", help="List known backups")
    s_list.add_argument("--json", action="store_true")
    s_list.set_defaults(func=cmd_list)

    s_diff = sub.add_parser("diff", help="Show change summary vs the latest backup (no new backup)")
    s_diff.set_defaults(func=cmd_diff)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
