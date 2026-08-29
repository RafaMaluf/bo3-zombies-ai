from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

GAMEPLAY_IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

SECRET_PATTERNS = (
    ("Groq API key", re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b")),
    ("Voyage API key", re.compile(r"\bpa-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"^\s*(GROQ_API_KEY|VOYAGE_API_KEY|R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY)"
    r"\s*=\s*(.*?)\s*$",
    flags=re.IGNORECASE,
)
SAFE_PLACEHOLDER_PREFIXES = (
    "${",
    "$",
    "<",
    "...",
    "changeme",
    "dummy",
    "example",
    "test",
    "your",
)


def forbidden_gameplay_images(paths: Iterable[str]) -> list[str]:
    forbidden: list[str] = []
    for raw_path in paths:
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        path = PurePosixPath(normalized)
        parts = path.parts
        if len(parts) < 2 or parts[0] != "maps":
            continue
        inside_images_directory = len(parts) >= 3 and parts[2] == "images"
        has_image_extension = path.suffix.lower() in GAMEPLAY_IMAGE_SUFFIXES
        if inside_images_directory or has_image_extension:
            forbidden.append(normalized)
    return sorted(set(forbidden))


def _is_safe_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'\"").lower()
    return not normalized or normalized in {"none", "null"} or normalized.startswith(
        SAFE_PLACEHOLDER_PREFIXES
    )


def potential_secrets(files: Iterable[tuple[str, bytes]]) -> list[str]:
    findings: set[str] = set()
    for raw_path, content in files:
        normalized_path = raw_path.strip().replace("\\", "/")
        if not normalized_path:
            continue
        filename = PurePosixPath(normalized_path).name.lower()
        if filename == ".env" or (filename.startswith(".env.") and filename != ".env.example"):
            findings.add(f"{normalized_path}: tracked environment file")
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.add(f"{normalized_path}:{line_number}: {label}")
            assignment = SENSITIVE_ASSIGNMENT.match(line)
            if assignment and not _is_safe_placeholder(assignment.group(2)):
                findings.add(
                    f"{normalized_path}:{line_number}: non-placeholder {assignment.group(1)}"
                )
    return sorted(findings)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [path.decode("utf-8") for path in result.stdout.split(b"\0") if path]


def tracked_file_contents(paths: Iterable[str]) -> list[tuple[str, bytes]]:
    contents: list[tuple[str, bytes]] = []
    for path in paths:
        try:
            contents.append((path, Path(path).read_bytes()))
        except OSError as error:
            raise RuntimeError(f"Could not inspect tracked file {path}: {error}") from error
    return contents


def main() -> int:
    paths = tracked_files()
    forbidden = forbidden_gameplay_images(paths)
    if forbidden:
        print("Tracked gameplay image binaries are forbidden:")
        for path in forbidden:
            print(f"- {path}")
        return 1
    secrets = potential_secrets(tracked_file_contents(paths))
    if secrets:
        print("Potential committed secrets are forbidden:")
        for finding in secrets:
            print(f"- {finding}")
        return 1
    print("Repository hygiene passed: no gameplay images or potential secrets are tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
