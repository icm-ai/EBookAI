import asyncio
import time
import uuid
from pathlib import Path

import ebooklib
import PyPDF2
from ebooklib import epub
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from utils.error_handler import handle_service_error
from utils.exceptions import (
    ConversionError,
    ConversionTimeoutError,
    FileProcessingError,
    ResourceNotFoundError,
    ValidationError,
)
from utils.logging_config import (
    get_logger,
    log_operation_end,
    log_operation_error,
    log_operation_start,
)
from utils.progress_tracker import progress_tracker

from config import ALLOWED_EXTENSIONS, CONVERSION_TIMEOUT, OUTPUT_DIR, UPLOAD_DIR


class ConversionService:
    """Handle ebook format conversion"""

    def __init__(self):
        self.logger = get_logger("conversion")
        self.upload_dir = Path(UPLOAD_DIR)
        self.output_dir = Path(OUTPUT_DIR)
        self.upload_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.chinese_font_name = self._register_chinese_fonts()

    async def convert_file(
        self, file_path: str, target_format: str, task_id: str = None
    ) -> dict:
        """Convert file between supported formats"""
        if not task_id:
            task_id = str(uuid.uuid4())

        start_time = time.time()
        operation = "file_conversion"

        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise ResourceNotFoundError(
                    message="Input file not found",
                    resource_type="file",
                    resource_id=str(file_path),
                )

            source_format = file_path.suffix.lower()
            target_format = target_format.lower()

            # Initialize progress tracking
            progress_tracker.start_task(
                task_id=task_id,
                file_name=file_path.name,
                source_format=source_format,
                target_format=target_format,
                total_steps=5,
            )

            # Validation
            if source_format not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    message=f"Unsupported source format: {source_format}",
                    field="source_format",
                    value=source_format,
                )

            if f".{target_format}" not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    message=f"Unsupported target format: {target_format}",
                    field="target_format",
                    value=target_format,
                )

            if source_format == f".{target_format}":
                raise ValidationError(
                    message="Source and target formats cannot be the same",
                    details={
                        "source_format": source_format,
                        "target_format": target_format,
                    },
                )

            # Update progress: Validation completed
            progress_tracker.update_progress(
                task_id, 1, "Validation completed, preparing conversion..."
            )

            # Generate output filename
            output_filename = f"{file_path.stem}_{task_id}.{target_format}"
            output_path = self.output_dir / output_filename

            # Update progress: File preparation
            progress_tracker.update_progress(
                task_id,
                2,
                f"Preparing {source_format} to {target_format} conversion...",
            )

            log_operation_start(
                self.logger,
                operation,
                task_id=task_id,
                source_format=source_format,
                target_format=target_format,
                input_file=str(file_path),
                output_file=output_filename,
            )

            # Update progress: Starting conversion
            progress_tracker.update_progress(
                task_id, 3, f"Converting from {source_format} to {target_format}...", 60
            )

            # Run conversion with timeout
            try:
                if source_format == ".epub" and target_format == "pdf":
                    await asyncio.wait_for(
                        self._epub_to_pdf(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".pdf" and target_format == "epub":
                    await asyncio.wait_for(
                        self._pdf_to_epub(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".txt" and target_format == "pdf":
                    await asyncio.wait_for(
                        self._txt_to_pdf(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".txt" and target_format == "epub":
                    await asyncio.wait_for(
                        self._txt_to_epub(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".epub" and target_format == "txt":
                    await asyncio.wait_for(
                        self._epub_to_txt(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".pdf" and target_format == "txt":
                    await asyncio.wait_for(
                        self._pdf_to_txt(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                # MOBI format conversions
                elif source_format == ".mobi" and target_format == "txt":
                    await asyncio.wait_for(
                        self._mobi_to_txt(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".mobi" and target_format == "pdf":
                    await asyncio.wait_for(
                        self._mobi_to_pdf(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                # AZW3 format conversions
                elif source_format == ".azw3" and target_format == "txt":
                    await asyncio.wait_for(
                        self._azw3_to_txt(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                elif source_format == ".azw3" and target_format == "pdf":
                    await asyncio.wait_for(
                        self._azw3_to_pdf(file_path, output_path),
                        timeout=CONVERSION_TIMEOUT,
                    )
                else:
                    raise ConversionError(
                        message=f"Conversion from {source_format} to {target_format} not supported",
                        source_format=source_format,
                        target_format=target_format,
                    )

                # Update progress: Finalizing
                progress_tracker.update_progress(
                    task_id, 4, "Finalizing conversion...", 90
                )

                duration = time.time() - start_time
                log_operation_end(
                    self.logger,
                    operation,
                    duration,
                    task_id=task_id,
                    output_file=output_filename,
                )

                # Complete progress tracking
                progress_tracker.complete_task(task_id, output_filename)

                return {
                    "task_id": task_id,
                    "status": "completed",
                    "output_file": output_filename,
                    "message": "Conversion completed successfully",
                }

            except asyncio.TimeoutError:
                progress_tracker.fail_task(
                    task_id, "Conversion timeout - operation took too long"
                )
                raise ConversionTimeoutError(
                    timeout_seconds=CONVERSION_TIMEOUT,
                    source_format=source_format,
                    target_format=target_format,
                )
            except Exception as e:
                progress_tracker.fail_task(task_id, f"Conversion failed: {str(e)}")
                if isinstance(e, (ConversionError, ConversionTimeoutError)):
                    raise
                raise ConversionError(
                    message=f"Conversion failed: {str(e)}",
                    source_format=source_format,
                    target_format=target_format,
                    original_error=e,
                )

        except Exception as e:
            # Update progress on any error
            if task_id:
                progress_tracker.fail_task(task_id, str(e))

            log_operation_error(
                self.logger,
                operation,
                e,
                task_id=task_id,
                source_format=source_format if "source_format" in locals() else None,
                target_format=target_format if "target_format" in locals() else None,
            )
            if isinstance(
                e,
                (
                    ValidationError,
                    ResourceNotFoundError,
                    ConversionError,
                    ConversionTimeoutError,
                ),
            ):
                raise

            raise handle_service_error(
                operation="file_conversion",
                error=e,
                task_id=task_id,
                source_format=source_format if "source_format" in locals() else None,
                target_format=target_format if "target_format" in locals() else None,
            )

    async def _epub_to_pdf(self, epub_path: Path, pdf_path: Path):
        """Convert EPUB to PDF"""
        try:
            # Read EPUB file
            book = epub.read_epub(str(epub_path))

            # Extract text content
            content = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # Simple text extraction (in production, use proper HTML parsing)
                    text = item.get_content().decode("utf-8")
                    # Remove HTML tags (basic approach)
                    import re

                    text = re.sub(r"<[^>]+>", "", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    if text:
                        content.append(text)

            # Create PDF with font support
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)

            # Use the registered Chinese font
            font_name = self.chinese_font_name

            title_style = ParagraphStyle(
                "ChineseTitle",
                fontName=font_name,
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor="black",
            )

            normal_style = ParagraphStyle(
                "ChineseNormal",
                fontName=font_name,
                fontSize=12,
                spaceAfter=12,
                alignment=TA_JUSTIFY,
                textColor="black",
                leading=16,
            )

            story = []

            # Add title
            title = book.get_metadata("DC", "title")
            if title:
                story.append(Paragraph(title[0][0], title_style))
                story.append(Spacer(1, 20))

            # Add content
            for text in content:
                if len(text) > 50:  # Filter out very short fragments
                    para = Paragraph(text, normal_style)
                    story.append(para)
                    story.append(Spacer(1, 12))

            doc.build(story)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to convert EPUB to PDF",
                file_path=str(epub_path),
                file_type="epub",
                original_error=e,
            )

    async def _pdf_to_epub(self, pdf_path: Path, epub_path: Path):
        """Convert PDF to EPUB"""
        try:
            # Read PDF
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract text from all pages
                text_content = []
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text.strip():
                        text_content.append(text)

            # Create EPUB
            book = epub.EpubBook()

            # Set metadata
            book.set_identifier(str(uuid.uuid4()))
            book.set_title(pdf_path.stem)
            book.set_language("en")
            book.add_author("Converted by EBookAI")

            # Create chapters from PDF pages
            chapters = []
            for i, text in enumerate(text_content):
                if text.strip():
                    chapter = epub.EpubHtml(
                        title=f"Chapter {i+1}", file_name=f"chap_{i+1}.xhtml", lang="en"
                    )

                    # Format text as HTML
                    html_content = f"""
                    <html>
                    <head>
                        <title>Chapter {i+1}</title>
                    </head>
                    <body>
                        <h1>Chapter {i+1}</h1>
                        <p>{text.replace('\n', '</p><p>')}</p>
                    </body>
                    </html>
                    """
                    chapter.content = html_content
                    book.add_item(chapter)
                    chapters.append(chapter)

            # Create table of contents
            book.toc = [(epub.Section("Chapters"), chapters)]

            # Add navigation
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Define CSS style
            style = """
            body { font-family: serif; margin: 1em; }
            h1 { color: #333; }
            p { text-align: justify; margin-bottom: 1em; }
            """
            nav_css = epub.EpubItem(
                uid="nav_css",
                file_name="style/nav.css",
                media_type="text/css",
                content=style,
            )
            book.add_item(nav_css)

            # Create spine
            book.spine = ["nav"] + chapters

            # Write EPUB file
            epub.write_epub(str(epub_path), book)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to convert PDF to EPUB",
                file_path=str(pdf_path),
                file_type="pdf",
                original_error=e,
            )

    async def extract_text_from_file(self, file_path: str) -> str:
        """Extract text content from ebook file"""
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                raise ResourceNotFoundError(
                    message="File not found",
                    resource_type="file",
                    resource_id=str(file_path),
                )

            file_format = file_path.suffix.lower()

            if file_format == ".epub":
                return await self._extract_text_from_epub(file_path)
            elif file_format == ".pdf":
                return await self._extract_text_from_pdf(file_path)
            else:
                raise ValidationError(
                    message=f"Unsupported file format for text extraction: {file_format}",
                    field="file_format",
                    value=file_format,
                )
        except Exception as e:
            if isinstance(e, (ValidationError, ResourceNotFoundError)):
                raise

            raise handle_service_error(
                operation="text_extraction",
                error=e,
                file_path=str(file_path),
            )

    async def _extract_text_from_epub(self, epub_path: Path) -> str:
        """Extract text from EPUB file"""
        try:
            book = epub.read_epub(str(epub_path))
            content = []

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    text = item.get_content().decode("utf-8")
                    # Remove HTML tags
                    import re

                    text = re.sub(r"<[^>]+>", "", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    if text:
                        content.append(text)

            return " ".join(content)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to extract text from EPUB",
                file_path=str(epub_path),
                file_type="epub",
                original_error=e,
            )

    async def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                content = []

                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content.append(text)

            return " ".join(content)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to extract text from PDF",
                file_path=str(pdf_path),
                file_type="pdf",
                original_error=e,
            )

    def cleanup_file(self, file_path: str):
        """Clean up uploaded or temporary files"""
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass  # Ignore cleanup errors

    def get_conversion_status(self, task_id: str) -> dict:
        """Get conversion task status (simplified implementation)"""
        # In a real implementation, this would check a database or cache
        return {"task_id": task_id, "status": "completed"}  # Simplified for MVP

    def _register_chinese_fonts(self):
        """Register Chinese fonts for PDF generation"""
        try:
            # Use ReportLab's built-in CID fonts for Chinese support
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont

            # Register STSong-Light font for Chinese (built into ReportLab)
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            print("Successfully registered STSong-Light CID font")
            return "STSong-Light"
        except Exception as e:
            print(f"CID font registration failed: {e}")

        try:
            # Try WQY ZenHei font with subfont index
            wqy_font_path = "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc"
            if Path(wqy_font_path).exists():
                pdfmetrics.registerFont(
                    TTFont("WQYZenHei", wqy_font_path, subfontIndex=0)
                )
                print("Successfully registered WQYZenHei font")
                return "WQYZenHei"
        except Exception as e:
            print(f"WQY ZenHei font registration failed: {e}")

        try:
            # Fallback to DejaVu font
            pdfmetrics.registerFont(
                TTFont("DejaVuSans", "/usr/share/fonts/dejavu/DejaVuSans.ttf")
            )
            print("Successfully registered DejaVuSans font")
            return "DejaVuSans"
        except Exception as e:
            print(f"DejaVu font registration failed: {e}")

        print("All font registrations failed, using built-in fonts")
        return "Helvetica"

    async def _txt_to_pdf(self, txt_path: Path, pdf_path: Path):
        """Convert TXT to PDF with Chinese font support"""
        try:
            # Read TXT file with robust encoding detection
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(txt_path, "r", encoding="gbk") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

            # Create PDF
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)

            # Use the registered Chinese font
            font_name = self.chinese_font_name

            title_style = ParagraphStyle(
                "ChineseTitle",
                fontName=font_name,
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor="black",
            )

            normal_style = ParagraphStyle(
                "ChineseNormal",
                fontName=font_name,
                fontSize=12,
                spaceAfter=12,
                alignment=TA_JUSTIFY,
                textColor="black",
                leading=16,
            )

            story = []

            # Add title (file name without extension)
            title = txt_path.stem
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 20))

            # Split content into paragraphs
            paragraphs = content.split("\n\n")
            for para_text in paragraphs:
                para_text = para_text.strip().replace("\n", "")
                if para_text:
                    para = Paragraph(para_text, normal_style)
                    story.append(para)
                    story.append(Spacer(1, 12))

            doc.build(story)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to convert TXT to PDF",
                file_path=str(txt_path),
                file_type="txt",
                original_error=e,
            )

    async def _txt_to_epub(self, txt_path: Path, epub_path: Path):
        """Convert TXT to EPUB"""
        try:
            # Read TXT file with robust encoding detection
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(txt_path, "r", encoding="gbk") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

            # Create EPUB
            book = epub.EpubBook()
            book.set_identifier(str(uuid.uuid4()))
            book.set_title(txt_path.stem)
            book.set_language("zh")
            book.add_author("文本转换")

            # Split content into chapters (every 5000 characters)
            chunk_size = 5000
            chapters = []
            for i in range(0, len(content), chunk_size):
                chapter_content = content[i : i + chunk_size]
                if chapter_content.strip():
                    chapter_num = i // chunk_size + 1

                    chapter = epub.EpubHtml(
                        title=f"第{chapter_num}章",
                        file_name=f"chap_{chapter_num:03d}.xhtml",
                        lang="zh",
                    )

                    # Format as HTML with proper Chinese styling
                    html_content = f"""
                    <html>
                    <head>
                        <title>第{chapter_num}章</title>
                        <style>
                            body {{
                                font-family: serif;
                                line-height: 1.8;
                                margin: 2em;
                                text-align: justify;
                            }}
                            h1 {{
                                color: #333;
                                text-align: center;
                                margin-bottom: 2em;
                            }}
                            p {{
                                text-indent: 2em;
                                margin-bottom: 1em;
                            }}
                        </style>
                    </head>
                    <body>
                        <h1>第{chapter_num}章</h1>
                        <p>{chapter_content.replace(chr(10), '</p><p>')}</p>
                    </body>
                    </html>
                    """

                    chapter.content = html_content
                    book.add_item(chapter)
                    chapters.append(chapter)

            # Create table of contents
            book.toc = [(epub.Section("章节"), chapters)]

            # Add navigation
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Create spine
            book.spine = ["nav"] + chapters

            # Write EPUB file
            epub.write_epub(str(epub_path), book)
        except Exception as e:
            raise FileProcessingError(
                message="Failed to convert TXT to EPUB",
                file_path=str(txt_path),
                file_type="txt",
                original_error=e,
            )

    async def _epub_to_txt(self, epub_path: Path, txt_path: Path):
        """Convert EPUB to TXT"""
        try:
            content = await self._extract_text_from_epub(epub_path)

            # Write to TXT file
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            if isinstance(e, FileProcessingError):
                raise
            raise FileProcessingError(
                message="Failed to convert EPUB to TXT",
                file_path=str(epub_path),
                file_type="epub",
                original_error=e,
            )

    async def _pdf_to_txt(self, pdf_path: Path, txt_path: Path):
        """Convert PDF to TXT"""
        try:
            content = await self._extract_text_from_pdf(pdf_path)

            # Write to TXT file
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            if isinstance(e, FileProcessingError):
                raise
            raise FileProcessingError(
                message="Failed to convert PDF to TXT",
                file_path=str(pdf_path),
                file_type="pdf",
                original_error=e,
            )

    # MOBI and AZW3 format handlers
    async def _mobi_to_txt(self, mobi_path: Path, txt_path: Path):
        """Convert MOBI to TXT - Basic text extraction"""
        try:
            text_content = self._extract_text_from_mobi(mobi_path)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text_content)
        except Exception as e:
            raise ConversionError(
                message="Failed to convert MOBI to TXT",
                source_format=".mobi",
                target_format="txt",
                file_path=str(mobi_path),
                original_error=e,
            )

    async def _azw3_to_txt(self, azw3_path: Path, txt_path: Path):
        """Convert AZW3 to TXT - Basic text extraction"""
        try:
            text_content = self._extract_text_from_azw3(azw3_path)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text_content)
        except Exception as e:
            raise ConversionError(
                message="Failed to convert AZW3 to TXT",
                source_format=".azw3",
                target_format="txt",
                file_path=str(azw3_path),
                original_error=e,
            )

    async def _mobi_to_pdf(self, mobi_path: Path, pdf_path: Path):
        """Convert MOBI to PDF"""
        try:
            text_content = self._extract_text_from_mobi(mobi_path)
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            font_name = self.chinese_font_name

            style = ParagraphStyle(
                "ChineseText",
                fontName=font_name,
                fontSize=12,
                leading=16,
                alignment=TA_JUSTIFY,
                spaceAfter=10,
            )

            paragraphs = text_content.split("\n\n")
            elements = []
            for para in paragraphs:
                if para.strip():
                    p = Paragraph(para.strip(), style)
                    elements.append(p)
                    elements.append(Spacer(1, 6))

            doc.build(elements)
        except Exception as e:
            raise ConversionError(
                message="Failed to convert MOBI to PDF",
                source_format=".mobi",
                target_format="pdf",
                file_path=str(mobi_path),
                original_error=e,
            )

    async def _azw3_to_pdf(self, azw3_path: Path, pdf_path: Path):
        """Convert AZW3 to PDF"""
        try:
            text_content = self._extract_text_from_azw3(azw3_path)
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            font_name = self.chinese_font_name

            style = ParagraphStyle(
                "ChineseText",
                fontName=font_name,
                fontSize=12,
                leading=16,
                alignment=TA_JUSTIFY,
                spaceAfter=10,
            )

            paragraphs = text_content.split("\n\n")
            elements = []
            for para in paragraphs:
                if para.strip():
                    p = Paragraph(para.strip(), style)
                    elements.append(p)
                    elements.append(Spacer(1, 6))

            doc.build(elements)
        except Exception as e:
            raise ConversionError(
                message="Failed to convert AZW3 to PDF",
                source_format=".azw3",
                target_format="pdf",
                file_path=str(azw3_path),
                original_error=e,
            )

    def _extract_text_from_mobi(self, mobi_path: Path) -> str:
        """Extract text from MOBI file - Basic implementation"""
        try:
            with open(mobi_path, "rb") as f:
                content = f.read()

            # Basic text extraction
            try:
                decoded = content.decode("utf-8", errors="ignore")
                import re

                readable_text = re.findall(r'[a-zA-Z0-9\s\.,!?;:"\'-]+', decoded)
                text_content = " ".join(readable_text)

                if len(text_content.strip()) < 100:
                    text_content = f"MOBI file: {mobi_path.name}\n\nThis is a converted MOBI file. Basic text extraction applied.\n\nOriginal file size: {len(content)} bytes"
            except Exception:
                text_content = f"MOBI file: {mobi_path.name}\n\nContent extraction from this MOBI file is not fully supported. Please consider converting to EPUB first."

            return text_content
        except Exception as e:
            raise FileProcessingError(
                message="Failed to extract text from MOBI",
                file_path=str(mobi_path),
                file_type="mobi",
                original_error=e,
            )

    def _extract_text_from_azw3(self, azw3_path: Path) -> str:
        """Extract text from AZW3 file - Basic implementation"""
        try:
            with open(azw3_path, "rb") as f:
                content = f.read()

            # Basic text extraction
            try:
                decoded = content.decode("utf-8", errors="ignore")
                import re

                readable_text = re.findall(r'[a-zA-Z0-9\s\.,!?;:"\'-]+', decoded)
                text_content = " ".join(readable_text)

                if len(text_content.strip()) < 100:
                    text_content = f"AZW3 file: {azw3_path.name}\n\nThis is a converted AZW3 file. Basic text extraction applied.\n\nOriginal file size: {len(content)} bytes"
            except Exception:
                text_content = f"AZW3 file: {azw3_path.name}\n\nContent extraction from this AZW3 file is not fully supported. Please consider converting to EPUB first."

            return text_content
        except Exception as e:
            raise FileProcessingError(
                message="Failed to extract text from AZW3",
                file_path=str(azw3_path),
                file_type="azw3",
                original_error=e,
            )
