#!/usr/bin/env python3
"""Offline, standard-library-only DSH Skill installer. Does not read credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

NAME = "gpt-flash-handoff"
ROOT = Path(__file__).absolute().parent
BEGIN = b"<!-- gpt-flash-handoff:begin -->"
END = b"<!-- gpt-flash-handoff:end -->"


def safe(path):
    """Refuse symlinks/junctions on the path or any existing ancestor."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing symlink/junction: " + str(part))
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload():
    source = safe(ROOT / NAME)
    manifest = json.loads(safe(ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("name") != NAME or manifest.get("version") != "1.0.0":
        raise ValueError("Unexpected package identity")
    entries = manifest["files"]
    expected = {"SKILL.md", "references/task-contract.md", "references/acceptance-handoff.md"}
    if set(entries) != expected:
        raise ValueError("Unexpected Skill payload file list")
    result = {}
    for relative in sorted(expected):
        data = safe(source / relative).read_bytes()
        if digest(data) != entries[relative]:
            raise ValueError("Payload checksum mismatch: " + relative)
        result[relative] = data
    block = safe(ROOT / "global-mode.md").read_bytes()
    if digest(block) != manifest["global_mode_sha256"]:
        raise ValueError("Global mode checksum mismatch")
    return source, result, block


def existing_payload(target):
    result = {}
    if target.exists() and not target.is_dir():
        raise ValueError("Skill target is not a directory")
    if target.exists():
        for path in target.rglob("*"):
            safe(path)
            if path.is_file():
                result[path.relative_to(target).as_posix()] = path.read_bytes()
    return result


def global_change(before, block, action):
    starts, ends = before.count(BEGIN), before.count(END)
    if starts != ends or starts > 1:
        raise ValueError("Duplicate or incomplete managed global block; manual review required")
    if action == "enable":
        if starts:
            start = before.index(BEGIN)
            if before[start:start + len(block)] != block:
                raise ValueError("Managed global block has been edited; refusing to overwrite")
            return before
        return before + (b"\n\n" if before else b"") + block
    if not starts:
        return before
    start = before.index(BEGIN)
    if before[start:start + len(block)] != block:
        raise ValueError("Managed global block has been edited; refusing to remove")
    # Installation appends exactly two LF bytes before its block in nonempty files.
    remove_start = start - 2 if start >= 2 and before[start - 2:start] == b"\n\n" else start
    return before[:remove_start] + before[start + len(block):]


def backup(path, data, directory):
    if directory is None:
        raise ValueError("Modifying existing AGENTS.md requires explicit --backup-dir")
    directory = safe(directory)
    target = safe(directory / ("AGENTS.md." + uuid.uuid4().hex + ".bak"))
    directory.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    print("BACKUP " + str(target))


def run(args):
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required for Windows junction safety")
    source, files, block = payload()
    home = safe(args.home or os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
    target = safe(home / "skills" / NAME)
    agents = safe(home / "AGENTS.md")
    print("DSH_HOME " + str(home))
    print("SKILL_TARGET " + str(target))
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("Installation target overlaps package source")
    old = existing_payload(target)
    if old and old != files:
        raise ValueError("Existing Skill differs or has extra files; refusing overwrite/removal")
    if target.exists() and not old:
        raise ValueError("Existing empty Skill directory; manual review required")
    if args.uninstall and not args.yes:
        raise ValueError("Uninstall requires --yes after reviewing SKILL_TARGET")
    if args.uninstall:
        global_action = "disable"
    elif args.global_mode:
        global_action = "enable"
    elif args.disable_global:
        global_action = "disable"
    else:
        global_action = None
    # Preflight all edits before making any changes. Never print AGENTS.md contents.
    before = agents.read_bytes() if global_action and agents.exists() else b""
    if global_action:
        before.decode("utf-8-sig")  # Refuse unknown encoding; preserve original bytes/BOM.
        after = global_change(before, block, global_action)
    else:
        after = before
    if after != before and agents.exists() and not args.backup_dir:
        raise ValueError("Modifying existing AGENTS.md requires explicit --backup-dir")
    if args.backup_dir:
        backup_dir = safe(args.backup_dir)
        if backup_dir == ROOT or ROOT in backup_dir.parents or backup_dir == target or target in backup_dir.parents:
            raise ValueError("Backup directory must be outside the package and installed Skill")
    if args.dry_run:
        print("DRY_RUN no writes; " + (global_action or "on-demand") + " mode")
        return
    if after != before:
        if agents.exists():
            backup(agents, before, args.backup_dir)
        home.mkdir(parents=True, exist_ok=True)
        # Recheck observed bytes before writing; no cross-process transaction is promised.
        current = agents.read_bytes() if agents.exists() else b""
        if current != before:
            raise ValueError("AGENTS.md changed during installation; aborting")
        if global_action == "enable" and not args.uninstall and not old:
            target.mkdir(parents=True, exist_ok=False)
            for relative, data in files.items():
                path = safe(target / relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(data)
            old = files
        agents.write_bytes(after)
        print("GLOBAL_MODE " + global_action)
    if args.uninstall:
        if old:
            # Exact absolute target printed above; content must still match before deletion.
            if existing_payload(target) != files:
                raise ValueError("Skill changed during uninstall; refusing deletion")
            shutil.rmtree(target)
        print("UNINSTALLED " + str(target))
    elif not args.disable_global:
        if not old:
            target.mkdir(parents=True, exist_ok=False)
            for relative, data in files.items():
                path = safe(target / relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(data)
        print("INSTALLED " + str(target))
    else:
        print("Global mode disabled; Skill files retained")
    print("No model routes, credentials, providers or engine settings were modified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", help="DSH user home (default DSH_HOME or ~/.dsh)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--global", dest="global_mode", action="store_true", help="Append managed global rules")
    mode.add_argument("--disable-global", action="store_true", help="Remove exact managed rules only")
    mode.add_argument("--uninstall", action="store_true", help="Disable global mode and delete unchanged Skill")
    parser.add_argument("--backup-dir", help="Backup location, required before editing existing AGENTS.md")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show targets without writes")
    parser.add_argument("--yes", action="store_true", help="Confirm removal of printed unchanged Skill target")
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
