"""Minimal EPUB3 compiler for BookIR.

The compiler intentionally depends only on the Python standard library. This
keeps BookIR publishing independent from Calibre and allows the legacy
conversion stack to coexist during migration.
"""

from __future__ import annotations

import html
import uuid
import zipfile
from pathlib import Path
from typing import Iterable, List, Sequence

from book.domain.models import Book, BookNode, NodeType


class EpubCompiler:
    """Compile BookIR into a standards-oriented reflowable EPUB3 package."""

    MIMETYPE = "application/epub+zip"

    def compile(self, book: Book, output_path: Path) -> Path:
        output_path = Path(output_path)
        if output_path.suffix.lower() != ".epub":
            raise ValueError("EPUB output path must end with .epub")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sections = self._sections(book)
        identifier = book.metadata.identifier or f"urn:uuid:{uuid.uuid4()}"
        language = book.metadata.language or "und"
        title = book.metadata.title or "Untitled"

        with zipfile.ZipFile(output_path, "w") as archive:
            archive.writestr(
                "mimetype",
                self.MIMETYPE,
                compress_type=zipfile.ZIP_STORED,
            )
            archive.writestr(
                "META-INF/container.xml",
                self._container_xml(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            archive.writestr(
                "EPUB/styles/book.css",
                self._stylesheet(),
                compress_type=zipfile.ZIP_DEFLATED,
            )

            manifest_items: List[str] = [
                (
                    '<item id="nav" href="nav.xhtml" '
                    'media-type="application/xhtml+xml" properties="nav"/>'
                ),
                '<item id="css" href="styles/book.css" media-type="text/css"/>',
            ]
            spine_items: List[str] = []

            for index, (section_title, nodes) in enumerate(sections, start=1):
                item_id = f"section-{index}"
                href = f"text/{item_id}.xhtml"
                archive.writestr(
                    f"EPUB/{href}",
                    self._section_xhtml(
                        title=section_title,
                        language=language,
                        nodes=nodes,
                    ),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
                manifest_items.append(
                    f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="{item_id}"/>')

            archive.writestr(
                "EPUB/nav.xhtml",
                self._nav_xhtml(title=title, language=language, sections=sections),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            archive.writestr(
                "EPUB/package.opf",
                self._package_opf(
                    identifier=identifier,
                    title=title,
                    author=book.metadata.author,
                    language=language,
                    manifest_items=manifest_items,
                    spine_items=spine_items,
                ),
                compress_type=zipfile.ZIP_DEFLATED,
            )

        return output_path

    def _sections(self, book: Book) -> List[tuple[str, Sequence[BookNode]]]:
        explicit_sections: List[tuple[str, Sequence[BookNode]]] = []
        loose_nodes: List[BookNode] = []

        for node in book.nodes:
            if node.type in {NodeType.CHAPTER, NodeType.PART, NodeType.SECTION}:
                explicit_sections.append(
                    (node.content.strip() or "Untitled Section", node.children)
                )
            else:
                loose_nodes.append(node)

        if loose_nodes:
            explicit_sections.insert(
                0,
                (
                    book.metadata.title or "Book",
                    loose_nodes,
                ),
            )

        if not explicit_sections:
            explicit_sections.append((book.metadata.title or "Book", []))

        return explicit_sections

    def _section_xhtml(
        self,
        *,
        title: str,
        language: str,
        nodes: Sequence[BookNode],
    ) -> str:
        body = "\n".join(self._render_node(node) for node in nodes)
        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xml:lang="{html.escape(language)}"
      lang="{html.escape(language)}">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
</head>
<body>
  <section epub:type="chapter" xmlns:epub="http://www.idpf.org/2007/ops">
    <h1>{html.escape(title)}</h1>
    {body}
  </section>
</body>
</html>
"""

    def _render_node(self, node: BookNode) -> str:
        content = html.escape(node.content).replace("\n", "<br/>")

        if node.type == NodeType.HEADING:
            level = int(node.attrs.get("level", 2))
            level = min(max(level, 2), 6)
            rendered = f"<h{level}>{content}</h{level}>"
        elif node.type == NodeType.BLOCKQUOTE:
            rendered = f"<blockquote>{content}</blockquote>"
        elif node.type == NodeType.FOOTNOTE:
            rendered = (
                '<aside epub:type="footnote" xmlns:epub="http://www.idpf.org/2007/ops">'
                f"{content}</aside>"
            )
        elif node.type == NodeType.PAGE_BREAK:
            rendered = '<span epub:type="pagebreak" xmlns:epub="http://www.idpf.org/2007/ops"/>'
        elif node.type in {NodeType.LIST, NodeType.LIST_ITEM}:
            tag = "li" if node.type == NodeType.LIST_ITEM else "div"
            rendered = f"<{tag}>{content}</{tag}>"
        else:
            rendered = f"<p>{content}</p>" if content else ""

        if node.children:
            rendered += "\n" + "\n".join(
                self._render_node(child) for child in node.children
            )
        return rendered

    def _nav_xhtml(
        self,
        *,
        title: str,
        language: str,
        sections: Sequence[tuple[str, Sequence[BookNode]]],
    ) -> str:
        items = "\n".join(
            f'<li><a href="text/section-{index}.xhtml">{html.escape(section_title)}</a></li>'
            for index, (section_title, _) in enumerate(sections, start=1)
        )
        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="{html.escape(language)}"
      lang="{html.escape(language)}">
<head><meta charset="utf-8"/><title>{html.escape(title)}</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{html.escape(title)}</h1>
    <ol>{items}</ol>
  </nav>
</body>
</html>
"""

    @staticmethod
    def _container_xml() -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    def _package_opf(
        self,
        *,
        identifier: str,
        title: str,
        author: str,
        language: str,
        manifest_items: Iterable[str],
        spine_items: Iterable[str],
    ) -> str:
        safe_identifier = html.escape(identifier)
        safe_title = html.escape(title)
        safe_author = html.escape(author)
        safe_language = html.escape(language)
        manifest = "\n    ".join(manifest_items)
        spine = "\n    ".join(spine_items)
        creator = f"<dc:creator>{safe_author}</dc:creator>" if safe_author else ""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{safe_identifier}</dc:identifier>
    <dc:title>{safe_title}</dc:title>
    <dc:language>{safe_language}</dc:language>
    {creator}
    <meta property="dcterms:modified">2000-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine>
    {spine}
  </spine>
</package>
"""

    @staticmethod
    def _stylesheet() -> str:
        return """body {
  line-height: 1.65;
  margin: 5%;
  orphans: 2;
  widows: 2;
}
p {
  margin: 0.65em 0;
}
h1, h2, h3, h4, h5, h6 {
  break-after: avoid;
  line-height: 1.3;
}
blockquote {
  margin: 1em 1.5em;
}
img, svg {
  max-width: 100%;
  height: auto;
}
"""
