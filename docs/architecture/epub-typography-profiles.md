# EPUB Typography Profiles

The BookIR EPUB 3 compiler supports optional, reader-relative body font-size
presets. They are intended for reflowable readers such as Apple Books.

| Profile | Body CSS | Default? |
| --- | --- | --- |
| `reader-default` | No `font-size` declaration (reader controls sizing) | Yes |
| `compact` | `font-size: 85%;` | No |
| `extra-compact` | `font-size: 75%;` | No |

## Usage (BookIR compiler API)

Run from the repository root:

```bash
PYTHONPATH=backend/src python - <<'PY'
from pathlib import Path

from book.compiler import EpubCompiler, TypographyProfile
from book.domain.models import Book, BookMetadata, BookNode, NodeType

book = Book(
    metadata=BookMetadata(title="Typography Profile Demo", language="en"),
    nodes=[
        BookNode(
            id="sample-paragraph",
            type=NodeType.PARAGRAPH,
            content="A reflowable paragraph with reader-adjustable text.",
        )
    ],
)
compiler = EpubCompiler()
compiler.compile(book, Path("reader-default.epub"))
compiler.compile(
    book,
    Path("compact.epub"),
    typography_profile=TypographyProfile.COMPACT,
)
compiler.compile(
    book,
    Path("extra-compact.epub"),
    typography_profile="extra-compact",
)
PY
```

`EpubCompiler.compile()` accepts a `TypographyProfile` enum or one of the
three string names. An unsupported value raises `ValueError` before writing
the EPUB. Omitting the argument produces byte-for-byte the same EPUB CSS and
packaging as the original default path.

## Reader behavior and scope

- Relative percentages are preferences, **not** guarantees of a particular
  pixel size or a fixed proportion in every reading application. Readers may
  override publishers' styles. The presets are intended to preserve manual
  font adjustment within the reader.
- Profile CSS is scoped to the body of the existing reflowable XHTML. This
  patch does not change chapter markup, image assets, math representations,
  navigation, OPF, metadata identifiers or the BookIR schema.
- This feature is available in the **BookIR compiler API**. It is **not yet**
  wired to the legacy conversion API or Web UI.
- Figure/table/formula semantic rendering and resource packaging are separate
  concerns tracked in [Issue #4](https://github.com/icm-ai/EBookAI/issues/4).
  This patch does not attempt to resolve them.
- In-place CSS editing of **third-party EPUB input files** is not part of this
  feature. The compiler only generates EPUB from BookIR.

## Verification

Automated targeted regression:

```bash
PYTHONPATH=backend/src pytest -q backend/tests/test_epub_compiler.py
```

Check that:

1. Default output contains no explicit font-size override; explicit
   `reader-default` is byte-for-byte identical to the original API call.
2. Compact presets add only a relative `body { font-size: ...%; }` CSS rule.
3. Unchanged EPUB entries are byte-for-byte identical across profile variants.
4. Invalid profiles fail before writing, and repeated builds are deterministic.

Device validation (manual, not claimed as automated): import `compact.epub`
and `extra-compact.epub` into Apple Books, compare the same paragraph and
screen size, and verify that the font adjustment controls remain usable. Also
inspect headings, code, images and any available formulas/tables.
