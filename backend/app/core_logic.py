from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfWriter


NUMERIC_TOKEN_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+)")
UNICODE_ESCAPE_RE = re.compile(r"\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2})")

SORT_BY_NAME = "name"
SORT_BY_MTIME_ASC = "mtime_asc"
SORT_BY_MTIME_DESC = "mtime_desc"


@dataclass(frozen=True)
class PDFItem:
    path: Path

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def mtime(self) -> float:
        return self.path.stat().st_mtime

    @property
    def mtime_label(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M:%S")

    @property
    def size_bytes(self) -> int:
        return self.path.stat().st_size


def extract_numeric_parts(filename_stem: str) -> tuple[int, ...] | None:
    match = NUMERIC_TOKEN_RE.search(filename_stem)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def lecture_name_sort_key(item: PDFItem) -> tuple[int, tuple[int, ...], str]:
    numeric_parts = extract_numeric_parts(item.stem)
    if numeric_parts is None:
        return (1, tuple(), item.stem.casefold())
    return (0, numeric_parts, item.stem.casefold())


def sort_items(items: list[PDFItem], mode: str = SORT_BY_NAME) -> list[PDFItem]:
    if mode == SORT_BY_MTIME_ASC:
        return sorted(items, key=lambda item: (item.mtime, item.stem.casefold()))
    if mode == SORT_BY_MTIME_DESC:
        return sorted(
            items, key=lambda item: (item.mtime, item.stem.casefold()), reverse=True
        )
    return sorted(items, key=lecture_name_sort_key)


def decode_unicode_escapes_for_display(text: str) -> str:
    """Render literal unicode escape sequences (e.g. \\u0531) as characters."""

    def replace_match(match: re.Match[str]) -> str:
        token = match.group(0)[1:]
        prefix = token[0]
        digits = token[1:]
        try:
            value = int(digits, 16)
            if prefix in {"u", "U", "x"}:
                return chr(value)
        except (ValueError, OverflowError):
            return match.group(0)
        return match.group(0)

    candidate = text
    for _ in range(3):
        if "\\" not in candidate or not UNICODE_ESCAPE_RE.search(candidate):
            break
        candidate = (
            candidate.replace("\\\\u", "\\u")
            .replace("\\\\U", "\\U")
            .replace("\\\\x", "\\x")
        )
        decoded = UNICODE_ESCAPE_RE.sub(replace_match, candidate)
        if decoded == candidate:
            break
        candidate = decoded
    return candidate


def list_pdf_items(folder: Path) -> list[PDFItem]:
    return [PDFItem(path=p) for p in folder.glob("*.pdf") if p.is_file()]


def merge_pdf_paths(input_paths: list[Path], output_path: Path) -> None:
    if not input_paths:
        raise ValueError("No input PDF files provided.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    try:
        for path in input_paths:
            if not path.exists():
                raise FileNotFoundError(f"Missing file: {path}")
            writer.append(str(path))
        with output_path.open("wb") as out_file:
            writer.write(out_file)
    finally:
        writer.close()
