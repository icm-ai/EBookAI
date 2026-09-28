from __future__ import annotations

from pathlib import Path

import fitz


PAGE_W = 595
PAGE_H = 842


def _new_doc(title: str):
    doc = fitz.open()
    doc.set_metadata({"title": title, "author": "EBookAI Golden Corpus"})
    return doc


def _page(doc):
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def _text(page, x, y, text, size=12, fontname="helv"):
    page.insert_text((x, y), text, fontsize=size, fontname=fontname)


def build_fixture(kind: str, path: Path) -> Path:
    builders = {
        "digital_basic": _digital_basic,
        "footnote": _footnote,
        "multi_column": _multi_column,
        "table_like": _table_like,
        "scanned_image": _scanned_image,
    }
    builders[kind](Path(path))
    return Path(path)


def _digital_basic(path: Path):
    doc = _new_doc("Golden Digital Book")
    for index in range(3):
        page = _page(doc)
        _text(page, 220, 28, "GOLDEN BOOK", 9)
        _text(page, 285, 815, f"Page {index + 1}", 9)
        if index == 0:
            _text(page, 60, 90, "Chapter 1", 22)
            _text(
                page, 60, 145, "A clean digital paragraph with source provenance.", 12
            )
            _text(
                page,
                60,
                735,
                "This paragraph continues across the page boundary without",
                12,
            )
        elif index == 1:
            _text(page, 60, 105, "losing its provenance.", 12)
            _text(page, 60, 180, "A second paragraph ends normally.", 12)
        else:
            _text(page, 60, 130, "Final paragraph for the digital golden fixture.", 12)
    doc.save(path)
    doc.close()


def _footnote(path: Path):
    doc = _new_doc("Golden Footnote")
    page = _page(doc)
    _text(page, 60, 90, "Chapter 1", 20)
    _text(page, 60, 155, "This sentence cites source evidence [1] in the body.", 12)
    _text(page, 60, 620, "[1] Footnote text preserved and associated.", 8)
    doc.save(path)
    doc.close()


def _multi_column(path: Path):
    doc = _new_doc("Golden Multi Column")
    page = _page(doc)
    _text(page, 60, 70, "Multi Column Example", 20)
    _text(page, 60, 140, "Left column first paragraph.", 12)
    _text(page, 320, 150, "Right column first paragraph.", 12)
    _text(page, 60, 230, "Left column second paragraph.", 12)
    _text(page, 320, 240, "Right column second paragraph.", 12)
    doc.save(path)
    doc.close()


def _table_like(path: Path):
    doc = _new_doc("Golden Table")
    page = _page(doc)
    _text(page, 60, 70, "Table Example", 20)
    xs = [60, 220, 360]
    ys = [130, 170, 210]
    values = [
        ["Name", "Score", "Status"],
        ["Alice", "95", "Pass"],
        ["Bob", "88", "Pass"],
    ]
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            _text(page, x + 4, y - 7, values[r][c], 11)
    for x in [60, 220, 360, 500]:
        page.draw_line((x, 105), (x, 225))
    for y in [105, 145, 185, 225]:
        page.draw_line((60, y), (500, y))
    doc.save(path)
    doc.close()


def _scanned_image(path: Path):
    source = _new_doc("Raster Source")
    page = _page(source)
    _text(page, 70, 100, "Scanned Golden Page", 22)
    _text(page, 70, 160, "This text exists only as pixels in the final PDF.", 12)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    png = pixmap.tobytes("png")
    source.close()

    doc = _new_doc("Golden Scanned Image")
    page = _page(doc)
    page.insert_image(page.rect, stream=png)
    doc.save(path)
    doc.close()
