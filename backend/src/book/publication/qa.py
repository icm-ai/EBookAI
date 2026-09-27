"""Publication-readiness and structural EPUB validation."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from xml.etree import ElementTree

from book.domain.models import Book
from book.publication.models import (
    PublicationFinding,
    PublicationReport,
    PublicationSeverity,
)
from book.quality import IssueSeverity, QualityReport


class PublicationQAEngine:
    """Evaluate reviewed BookIR and optionally its compiled EPUB package."""

    REQUIRED_EPUB_FILES = {
        "mimetype",
        "META-INF/container.xml",
        "EPUB/package.opf",
        "EPUB/nav.xhtml",
    }

    def analyze(
        self,
        book: Book,
        quality_report: QualityReport,
        *,
        issue_resolutions: Optional[Dict[str, str]] = None,
        epub_path: Optional[Path] = None,
    ) -> PublicationReport:
        resolutions = issue_resolutions or {}
        findings: List[PublicationFinding] = []

        if not book.metadata.title.strip():
            findings.append(
                self._error(
                    "missing_title",
                    "Publication metadata requires a non-empty title.",
                )
            )
        if not book.nodes:
            findings.append(
                self._error(
                    "empty_book",
                    "Publication output contains no BookIR nodes.",
                )
            )
        if not book.metadata.language or book.metadata.language == "und":
            findings.append(
                self._warning(
                    "undefined_language",
                    "Book language is undefined; set a BCP 47 language before release.",
                )
            )

        findings.extend(
            self._quality_findings(
                quality_report,
                resolutions,
            )
        )

        epub_checked = epub_path is not None
        if epub_path is not None:
            findings.extend(self._validate_epub(Path(epub_path)))

        release_ready = not any(
            finding.severity == PublicationSeverity.ERROR for finding in findings
        )
        return PublicationReport(
            release_ready=release_ready,
            findings=findings,
            epub_checked=epub_checked,
        )

    def _quality_findings(
        self,
        report: QualityReport,
        resolutions: Dict[str, str],
    ) -> Iterable[PublicationFinding]:
        for issue in report.issues:
            state = resolutions.get(issue.id, "open")
            evidence = {
                "issue_id": issue.id,
                "issue_code": issue.code,
                "resolution": state,
                "node_ids": list(issue.node_ids),
            }

            if issue.severity == IssueSeverity.ERROR:
                yield self._error(
                    "blocking_quality_error",
                    f"Blocking quality error remains: {issue.message}",
                    evidence,
                )
            elif issue.severity == IssueSeverity.REVIEW:
                if state == "waived":
                    yield self._warning(
                        "waived_review_issue",
                        f"Reviewer explicitly waived: {issue.message}",
                        evidence,
                    )
                else:
                    yield self._error(
                        "unresolved_review_issue",
                        f"Review issue must be resolved or waived: {issue.message}",
                        evidence,
                    )
            else:
                yield PublicationFinding(
                    code="quality_info",
                    severity=PublicationSeverity.INFO,
                    message=issue.message,
                    evidence=evidence,
                )

    def _validate_epub(self, path: Path) -> List[PublicationFinding]:
        findings: List[PublicationFinding] = []
        if not path.is_file():
            return [
                self._error(
                    "epub_missing",
                    "Compiled EPUB file does not exist.",
                    {"path": str(path)},
                )
            ]

        try:
            archive = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile:
            return [
                self._error(
                    "epub_not_zip",
                    "EPUB is not a valid ZIP container.",
                    {"path": str(path)},
                )
            ]

        with archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)

            if len(names) != len(name_set):
                findings.append(
                    self._error(
                        "epub_duplicate_entries",
                        "EPUB contains duplicate ZIP entry names.",
                    )
                )

            if not infos or infos[0].filename != "mimetype":
                findings.append(
                    self._error(
                        "epub_mimetype_order",
                        "EPUB mimetype must be the first ZIP entry.",
                    )
                )
            else:
                if infos[0].compress_type != zipfile.ZIP_STORED:
                    findings.append(
                        self._error(
                            "epub_mimetype_compressed",
                            "EPUB mimetype entry must be stored without compression.",
                        )
                    )
                try:
                    mimetype = archive.read("mimetype").decode("ascii")
                except (KeyError, UnicodeDecodeError):
                    mimetype = ""
                if mimetype != "application/epub+zip":
                    findings.append(
                        self._error(
                            "epub_mimetype_value",
                            "EPUB mimetype entry has an invalid value.",
                            {"value": mimetype},
                        )
                    )

            missing = sorted(self.REQUIRED_EPUB_FILES - name_set)
            if missing:
                findings.append(
                    self._error(
                        "epub_required_files",
                        "EPUB is missing required package files.",
                        {"missing": missing},
                    )
                )
                return findings

            container_root = self._parse_xml(
                archive,
                "META-INF/container.xml",
                findings,
            )
            package_root = self._parse_xml(
                archive,
                "EPUB/package.opf",
                findings,
            )
            self._parse_xml(
                archive,
                "EPUB/nav.xhtml",
                findings,
            )

            if container_root is not None:
                rootfile = container_root.find(
                    "{urn:oasis:names:tc:opendocument:xmlns:container}rootfiles/"
                    "{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
                )
                full_path = (
                    rootfile.attrib.get("full-path") if rootfile is not None else None
                )
                if not full_path or full_path not in name_set:
                    findings.append(
                        self._error(
                            "epub_container_rootfile",
                            "container.xml does not point to an existing package document.",
                            {"full_path": full_path},
                        )
                    )

            if package_root is not None:
                findings.extend(
                    self._validate_package_manifest(
                        archive,
                        package_root,
                        name_set,
                    )
                )

        return findings

    def _validate_package_manifest(
        self,
        archive: zipfile.ZipFile,
        package_root: ElementTree.Element,
        name_set: set[str],
    ) -> List[PublicationFinding]:
        findings: List[PublicationFinding] = []
        namespace = {"opf": "http://www.idpf.org/2007/opf"}
        manifest_items = package_root.findall("opf:manifest/opf:item", namespace)
        spine_items = package_root.findall("opf:spine/opf:itemref", namespace)
        manifest = {
            item.attrib.get("id", ""): item.attrib.get("href", "")
            for item in manifest_items
            if item.attrib.get("id")
        }

        if not manifest:
            findings.append(
                self._error(
                    "epub_empty_manifest",
                    "EPUB package manifest is empty.",
                )
            )
        if not spine_items:
            findings.append(
                self._error(
                    "epub_empty_spine",
                    "EPUB package spine is empty.",
                )
            )

        for item_id, href in manifest.items():
            if not href:
                findings.append(
                    self._error(
                        "epub_manifest_href",
                        "Manifest item is missing href.",
                        {"item_id": item_id},
                    )
                )
                continue
            package_path = f"EPUB/{href}"
            if package_path not in name_set:
                findings.append(
                    self._error(
                        "epub_manifest_missing_resource",
                        "Manifest references a missing resource.",
                        {"item_id": item_id, "href": href},
                    )
                )
                continue
            if href.endswith(".xhtml"):
                self._parse_xml(archive, package_path, findings)

        for itemref in spine_items:
            idref = itemref.attrib.get("idref", "")
            if idref not in manifest:
                findings.append(
                    self._error(
                        "epub_spine_idref",
                        "Spine references an unknown manifest id.",
                        {"idref": idref},
                    )
                )

        return findings

    def _parse_xml(
        self,
        archive: zipfile.ZipFile,
        name: str,
        findings: List[PublicationFinding],
    ) -> Optional[ElementTree.Element]:
        try:
            return ElementTree.fromstring(archive.read(name))
        except KeyError:
            findings.append(
                self._error(
                    "epub_xml_missing",
                    f"Required XML resource is missing: {name}",
                )
            )
        except ElementTree.ParseError as exc:
            findings.append(
                self._error(
                    "epub_xml_invalid",
                    f"XML resource is not well formed: {name}",
                    {"error": str(exc)},
                )
            )
        return None

    @staticmethod
    def _error(
        code: str,
        message: str,
        evidence: Optional[Dict] = None,
    ) -> PublicationFinding:
        return PublicationFinding(
            code=code,
            severity=PublicationSeverity.ERROR,
            message=message,
            evidence=evidence or {},
        )

    @staticmethod
    def _warning(
        code: str,
        message: str,
        evidence: Optional[Dict] = None,
    ) -> PublicationFinding:
        return PublicationFinding(
            code=code,
            severity=PublicationSeverity.WARNING,
            message=message,
            evidence=evidence or {},
        )
