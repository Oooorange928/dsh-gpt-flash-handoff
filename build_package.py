#!/usr/bin/env python3
"""Build this portable package from an explicit allowlist; no credentials or network."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

NAME = "gpt-flash-handoff"
VERSION = "1.0.0"
ROOT = Path(__file__).absolute().parent
PAYLOAD = ("SKILL.md", "references/task-contract.md", "references/acceptance-handoff.md")
ALLOWLIST = (
    "README.md", "LICENSE", "install.py", "test_install.py", "build_package.py",
    "manifest.json", "VALIDATION.md", "global-mode.md",
    *(NAME + "/" + relative for relative in PAYLOAD),
)


def safe_file(relative):
    path = ROOT / relative
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing linked source: " + relative)
    if not path.is_file():
        raise ValueError("Missing package file: " + relative)
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    files = {relative: sha(safe_file(NAME + "/" + relative).read_bytes()) for relative in PAYLOAD}
    block = safe_file("global-mode.md").read_bytes()
    if not block.startswith(b"<!-- gpt-flash-handoff:begin -->\n") or not block.endswith(b"<!-- gpt-flash-handoff:end -->\n"):
        raise ValueError("Global block markers are invalid")
    result = {"name": NAME, "version": VERSION, "files": files, "global_mode_sha256": sha(block)}
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    destination = ROOT / "manifest.json"
    if destination.exists():
        safe_file("manifest.json")
        if destination.read_bytes() == data:
            return
    destination.write_bytes(data)


def contents():
    result = {}
    # Coarse privacy guard. A manual review remains required; this is not secret detection proof.
    private_patterns = (
        r"(?i)[a-z]:[\\/]", r"/(?:home|Users)/[a-zA-Z0-9_.-]+/",
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b", r"\bsk-[a-zA-Z0-9]{16,}\b",
        r"\bgh[pousr]_[a-zA-Z0-9]{20,}\b",
    )
    for relative in ALLOWLIST:
        data = safe_file(relative).read_bytes()
        text = data.decode("utf-8")
        if any(re.search(pattern, text) for pattern in private_patterns):
            raise ValueError("Review possible private machine data in: " + relative)
        result[NAME + "/" + relative] = data
    return result


def build():
    entries = contents()
    output = ROOT.parent / (NAME + "-" + VERSION + ".zip")
    for part in (output, *output.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Refusing linked ZIP output")
    if output.exists():
        with zipfile.ZipFile(output) as archive:
            current = {item.filename: archive.read(item) for item in archive.infolist()}
            if len(archive.infolist()) != len(entries) or current != entries:
                raise ValueError("Existing ZIP differs; review and move it before rebuilding")
        print("UNCHANGED " + output.name)
    else:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                item = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.create_system = 3
                item.external_attr = 0o100644 << 16
                archive.writestr(item, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        actual = {item.filename: archive.read(item) for item in archive.infolist()}
        if len(archive.infolist()) != len(entries) or actual != entries:
            raise ValueError("ZIP content verification failed")
    print("ZIP " + output.name)
    print("FILES " + str(len(entries)))
    print("BYTES " + str(output.stat().st_size))
    print("SHA256 " + sha(output.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-only", action="store_true", help="Refresh checksums without making ZIP")
    args = parser.parse_args()
    try:
        manifest()
        print("MANIFEST verified/refreshed")
        if not args.manifest_only:
            build()
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
