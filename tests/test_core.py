from pathlib import Path

from pypdf import PdfReader, PdfWriter

from backend.app.core_logic import (
    PDFItem,
    decode_unicode_escapes_for_display,
    merge_pdf_paths,
    sort_items,
)


def write_single_page_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)


def test_sort_items_numeric_name_priority(tmp_path: Path) -> None:
    paths = [
        tmp_path / "Lecture 10.2.pdf",
        tmp_path / "Lecture 2.1.pdf",
        tmp_path / "Intro.pdf",
    ]
    for path in paths:
        write_single_page_pdf(path)

    items = [PDFItem(path=p) for p in paths]
    sorted_items = sort_items(items, "name")
    assert [item.path.name for item in sorted_items] == [
        "Lecture 2.1.pdf",
        "Lecture 10.2.pdf",
        "Intro.pdf",
    ]


def test_decode_unicode_escapes_for_display() -> None:
    assert decode_unicode_escapes_for_display("\\u053C\\u0565\\u056F") == "Լեկ"


def test_merge_pdf_paths_creates_expected_pages(tmp_path: Path) -> None:
    first = tmp_path / "one.pdf"
    second = tmp_path / "two.pdf"
    out = tmp_path / "merged.pdf"

    write_single_page_pdf(first)
    write_single_page_pdf(second)

    merge_pdf_paths([first, second], out)

    reader = PdfReader(str(out))
    assert len(reader.pages) == 2
