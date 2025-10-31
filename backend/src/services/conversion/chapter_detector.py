"""
Chapter Detector Module - Intelligent chapter detection for PDF documents

This module provides sophisticated chapter detection using multiple methods:
- PDF bookmark/outline extraction
- Font size and style analysis
- Page break patterns
- AI-based content analysis
- Confidence scoring for each method
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from utils.logging_config import get_logger


@dataclass
class ChapterBoundary:
    """Represents a detected chapter boundary"""
    page_num: int
    title: str
    confidence: float
    detection_method: str
    level: int  # 1 for main chapters, 2 for subsections, etc.
    position_y: Optional[float] = None
    font_size: Optional[float] = None
    is_bold: Optional[bool] = None


@dataclass
class ChapterStructure:
    """Complete chapter structure of the document"""
    chapters: List[ChapterBoundary]
    total_confidence: float
    detection_methods_used: List[str]
    metadata: Dict[str, Any]


class ChapterDetector:
    """Intelligent chapter detector using multiple analysis methods"""

    def __init__(self, ai_service=None):
        self.logger = get_logger("chapter_detector")
        self.ai_service = ai_service

    def detect_chapters(self, pdf_doc, text_blocks: List, metadata: Dict = None) -> ChapterStructure:
        """
        Detect chapter boundaries using multiple methods

        Args:
            pdf_doc: PDF document object (PyMuPDF)
            text_blocks: List of text blocks with font information
            metadata: PDF metadata (optional)

        Returns:
            ChapterStructure with detected chapters
        """
        try:
            self.logger.info("Starting chapter detection")

            # Method 1: Extract bookmarks/outline
            bookmark_chapters = self._extract_bookmarks(pdf_doc)

            # Method 2: Font-based detection
            font_chapters = self._detect_by_font_analysis(text_blocks)

            # Method 3: Page break pattern analysis
            pattern_chapters = self._detect_by_page_patterns(pdf_doc, text_blocks)

            # Method 4: AI-based analysis (if available)
            ai_chapters = []
            if self.ai_service:
                ai_chapters = self._detect_by_ai_analysis(text_blocks)

            # Combine results from all methods
            combined_chapters = self._combine_detection_methods(
                bookmark_chapters, font_chapters, pattern_chapters, ai_chapters
            )

            # Calculate overall confidence
            total_confidence = self._calculate_overall_confidence(combined_chapters)

            # Create structure object
            structure = ChapterStructure(
                chapters=combined_chapters,
                total_confidence=total_confidence,
                detection_methods_used=self._get_used_methods([
                    bookmark_chapters, font_chapters, pattern_chapters, ai_chapters
                ]),
                metadata={
                    'bookmark_count': len(bookmark_chapters),
                    'font_detected_count': len(font_chapters),
                    'pattern_detected_count': len(pattern_chapters),
                    'ai_detected_count': len(ai_chapters)
                }
            )

            self.logger.info(f"Chapter detection complete: {len(combined_chapters)} chapters, "
                           f"confidence: {total_confidence:.1f}%")

            return structure

        except Exception as e:
            self.logger.error(f"Chapter detection failed: {str(e)}")
            # Return empty structure with low confidence
            return ChapterStructure(
                chapters=[],
                total_confidence=0.0,
                detection_methods_used=[],
                metadata={'error': str(e)}
            )

    def _extract_bookmarks(self, pdf_doc) -> List[ChapterBoundary]:
        """Extract chapter information from PDF bookmarks/outline"""
        chapters = []

        try:
            toc = pdf_doc.get_toc()

            for item in toc:
                level, title, page = item

                # Clean up title
                title = title.strip()
                if not title:
                    continue

                # Skip very short or numeric-only titles
                if len(title) < 2 or title.isdigit():
                    continue

                # Calculate confidence based on title quality
                confidence = self._calculate_bookmark_confidence(title, level)

                chapter = ChapterBoundary(
                    page_num=page - 1,  # Convert to 0-indexed
                    title=title,
                    confidence=confidence,
                    detection_method="bookmark",
                    level=level
                )
                chapters.append(chapter)

            self.logger.debug(f"Extracted {len(chapters)} bookmarks")
            return chapters

        except Exception as e:
            self.logger.warning(f"Bookmark extraction failed: {str(e)}")
            return []

    def _calculate_bookmark_confidence(self, title: str, level: int) -> float:
        """Calculate confidence score for bookmark-based chapter"""
        confidence = 90.0  # Base confidence for bookmarks

        # Adjust based on title characteristics
        if re.match(r'^(Chapter|第|章|Part|部分|Section|节)\s*\d+', title, re.IGNORECASE):
            confidence += 5  # Clear chapter indicators

        # Lower confidence for very short titles
        if len(title) < 5:
            confidence -= 10

        # Adjust based on level (deeper levels might be subsections)
        if level > 2:
            confidence -= 5

        return max(0, min(100, confidence))

    def _detect_by_font_analysis(self, text_blocks: List) -> List[ChapterBoundary]:
        """Detect chapters based on font size and style analysis"""
        chapters = []

        if not text_blocks:
            return chapters

        try:
            # Analyze font sizes to identify headings
            font_sizes = [block.font_size for block in text_blocks if block.font_size > 0]

            if not font_sizes:
                return chapters

            # Calculate statistics
            avg_font_size = sum(font_sizes) / len(font_sizes)
            max_font_size = max(font_sizes)

            # Potential heading threshold (significantly larger than average)
            heading_threshold = avg_font_size + (max_font_size - avg_font_size) * 0.3

            # Group text blocks by page
            pages = {}
            for block in text_blocks:
                if block.page_num not in pages:
                    pages[block.page_num] = []
                pages[block.page_num].append(block)

            # Look for headings on each page
            for page_num, page_blocks in pages.items():
                page_headings = []

                for block in page_blocks:
                    if (block.font_size >= heading_threshold and
                        block.is_bold and
                        len(block.text.strip()) > 2):

                        # Additional checks for heading quality
                        if self._is_likely_heading(block.text):
                            confidence = self._calculate_font_confidence(
                                block.font_size, avg_font_size, max_font_size, block.is_bold
                            )

                            heading = ChapterBoundary(
                                page_num=page_num,
                                title=block.text.strip(),
                                confidence=confidence,
                                detection_method="font_analysis",
                                level=1,  # Default level
                                position_y=block.y0,
                                font_size=block.font_size,
                                is_bold=block.is_bold
                            )
                            page_headings.append(heading)

                # Keep the best heading per page (largest font size)
                if page_headings:
                    best_heading = max(page_headings, key=lambda h: h.font_size)
                    chapters.append(best_heading)

            self.logger.debug(f"Font analysis detected {len(chapters)} chapters")
            return chapters

        except Exception as e:
            self.logger.warning(f"Font analysis failed: {str(e)}")
            return []

    def _is_likely_heading(self, text: str) -> bool:
        """Check if text is likely a heading based on content patterns"""
        text = text.strip()

        # Common chapter patterns
        chapter_patterns = [
            r'^(Chapter|章|第\s*\d+章|Part|部分|Section|节)\s*\d+',
            r'^\d+\.\s+',  # "1. "
            r'^[IVXLCDM]+\.\s+',  # Roman numerals
            r'^[A-Z]\.\s+',  # "A. "
        ]

        for pattern in chapter_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True

        # Check if text is short and doesn't look like a sentence
        if (len(text) < 100 and
            not text.endswith(('.', '!', '?', '。', '！', '？')) and
            not any(word in text.lower() for word in ['the', 'and', 'or', 'but', 'because'])):
            return True

        return False

    def _calculate_font_confidence(self, font_size: float, avg_size: float, max_size: float, is_bold: bool) -> float:
        """Calculate confidence score for font-based detection"""
        # Base confidence based on how much larger than average
        size_ratio = (font_size - avg_size) / (max_size - avg_size) if max_size > avg_size else 0
        confidence = 50 + (size_ratio * 40)  # 50-90 range

        # Boost for bold text
        if is_bold:
            confidence += 10

        return max(0, min(100, confidence))

    def _detect_by_page_patterns(self, pdf_doc, text_blocks: List) -> List[ChapterBoundary]:
        """Detect chapters based on page break patterns and content analysis"""
        chapters = []

        try:
            # Look for pages that start with larger fonts
            pages = {}
            for block in text_blocks:
                if block.page_num not in pages:
                    pages[block.page_num] = []
                pages[block.page_num].append(block)

            # Analyze page starts for chapter indicators
            for page_num in sorted(pages.keys()):
                page_blocks = pages[page_num]

                # Get blocks at the top of the page
                top_blocks = [b for b in page_blocks if b.y0 < 200]  # Top 200 points

                if top_blocks:
                    # Find the largest block at the top
                    top_block = max(top_blocks, key=lambda b: b.font_size)

                    # Check if it looks like a chapter start
                    if (top_block.font_size > 14 and
                        self._is_likely_heading(top_block.text)):

                        confidence = 60  # Moderate confidence for pattern detection

                        chapter = ChapterBoundary(
                            page_num=page_num,
                            title=top_block.text.strip(),
                            confidence=confidence,
                            detection_method="page_pattern",
                            level=1,
                            position_y=top_block.y0,
                            font_size=top_block.font_size
                        )
                        chapters.append(chapter)

            self.logger.debug(f"Pattern analysis detected {len(chapters)} chapters")
            return chapters

        except Exception as e:
            self.logger.warning(f"Page pattern analysis failed: {str(e)}")
            return []

    def _detect_by_ai_analysis(self, text_blocks: List) -> List[ChapterBoundary]:
        """Use AI to detect chapters when other methods fail"""
        chapters = []

        if not self.ai_service or not text_blocks:
            return chapters

        try:
            # Group text by pages for AI analysis
            pages_text = {}
            for block in text_blocks:
                if block.page_num not in pages_text:
                    pages_text[block.page_num] = []
                pages_text[block.page_num].append(block.text)

            # Analyze first few pages for chapter boundaries
            sample_pages = sorted(pages_text.keys())[:20]  # First 20 pages

            if len(sample_pages) < 3:
                return chapters

            # Prepare text for AI analysis
            sample_text = ""
            for page_num in sample_pages:
                page_text = ' '.join(pages_text[page_num])
                sample_text += f"Page {page_num + 1}:\n{page_text[:200]}...\n\n"

            # Use AI to identify chapter starts
            prompt = f"""
            Analyze this document sample and identify chapter boundaries.
            Look for chapter titles, section headings, or major topic changes.
            Return the page numbers and titles where chapters begin.

            Document sample:
            {sample_text}

            Format your response as:
            Page X: [Chapter Title]
            Page Y: [Chapter Title]
            ...

            Only return definite chapter starts, be conservative.
            """

            try:
                # Call AI service (implementation depends on your AI service interface)
                response = self.ai_service.analyze_text(prompt)

                # Parse AI response
                ai_chapters = self._parse_ai_response(response, pages_text)

                # Create ChapterBoundary objects
                for page_num, title in ai_chapters:
                    chapter = ChapterBoundary(
                        page_num=page_num,
                        title=title,
                        confidence=70,  # Moderate confidence for AI detection
                        detection_method="ai_analysis",
                        level=1
                    )
                    chapters.append(chapter)

            except Exception as e:
                self.logger.warning(f"AI service call failed: {str(e)}")

            self.logger.debug(f"AI analysis detected {len(chapters)} chapters")
            return chapters

        except Exception as e:
            self.logger.warning(f"AI analysis failed: {str(e)}")
            return []

    def _parse_ai_response(self, response: str, pages_text: Dict) -> List[Tuple[int, str]]:
        """Parse AI response to extract chapter information"""
        chapters = []

        try:
            lines = response.strip().split('\n')
            for line in lines:
                # Look for "Page X: Title" pattern
                match = re.match(r'Page\s*(\d+):\s*(.+)', line.strip(), re.IGNORECASE)
                if match:
                    page_num = int(match.group(1)) - 1  # Convert to 0-indexed
                    title = match.group(2).strip()

                    # Verify page exists and get actual title
                    if page_num in pages_text and pages_text[page_num]:
                        # Use first few words from actual page as title if AI response is too generic
                        if len(title) < 3 or title.lower() in ['chapter', 'section', 'part']:
                            actual_text = ' '.join(pages_text[page_num])[:100]
                            title = actual_text.split('.')[0].strip()

                        if title and len(title) > 2:
                            chapters.append((page_num, title))

        except Exception as e:
            self.logger.warning(f"Failed to parse AI response: {str(e)}")

        return chapters

    def _combine_detection_methods(self, bookmark_chapters, font_chapters, pattern_chapters, ai_chapters) -> List[ChapterBoundary]:
        """Combine results from different detection methods"""
        all_chapters = []

        # Priority: Bookmarks > Font Analysis > Page Patterns > AI Analysis

        # Start with bookmarks (highest priority)
        if bookmark_chapters:
            all_chapters.extend(bookmark_chapters)

        # Add font-based chapters that don't conflict with bookmarks
        if font_chapters:
            for font_chapter in font_chapters:
                if not self._conflicts_with_existing(font_chapter, all_chapters):
                    all_chapters.append(font_chapter)

        # Add pattern-based chapters
        if pattern_chapters:
            for pattern_chapter in pattern_chapters:
                if not self._conflicts_with_existing(pattern_chapter, all_chapters):
                    all_chapters.append(pattern_chapter)

        # Add AI-based chapters as fallback
        if ai_chapters:
            for ai_chapter in ai_chapters:
                if not self._conflicts_with_existing(ai_chapter, all_chapters):
                    all_chapters.append(ai_chapter)

        # Sort by page number
        all_chapters.sort(key=lambda c: c.page_num)

        # Remove duplicates and improve titles
        all_chapters = self._deduplicate_and_improve(all_chapters)

        return all_chapters

    def _conflicts_with_existing(self, chapter: ChapterBoundary, existing: List[ChapterBoundary]) -> bool:
        """Check if a chapter conflicts with existing ones"""
        for existing_chapter in existing:
            # Same page and similar title - likely duplicate
            if (chapter.page_num == existing_chapter.page_num and
                self._titles_similar(chapter.title, existing_chapter.title)):
                return True

            # Very close pages (within 2 pages) with similar titles
            if (abs(chapter.page_num - existing_chapter.page_num) <= 2 and
                self._titles_similar(chapter.title, existing_chapter.title)):
                return True

        return False

    def _titles_similar(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """Check if two titles are similar"""
        title1 = title1.lower().strip()
        title2 = title2.lower().strip()

        if title1 == title2:
            return True

        # Simple similarity check
        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def _deduplicate_and_improve(self, chapters: List[ChapterBoundary]) -> List[ChapterBoundary]:
        """Remove duplicates and improve chapter titles"""
        if not chapters:
            return chapters

        improved = []
        seen_titles = set()

        for chapter in chapters:
            title = chapter.title.lower().strip()

            # Skip if very similar to already seen title
            is_duplicate = False
            for seen_title in seen_titles:
                if self._titles_similar(title, seen_title, 0.9):
                    is_duplicate = True
                    break

            if not is_duplicate:
                # Clean up title
                chapter.title = self._clean_chapter_title(chapter.title)
                seen_titles.add(chapter.title.lower())
                improved.append(chapter)

        return improved

    def _clean_chapter_title(self, title: str) -> str:
        """Clean and normalize chapter title"""
        title = title.strip()

        # Remove page numbers
        title = re.sub(r'^Page\s*\d+\s*[:\-]?\s*', '', title, flags=re.IGNORECASE)

        # Fix common formatting issues
        title = re.sub(r'\s+', ' ', title)  # Multiple spaces to single space
        title = title.strip('•·-—–')  # Remove leading bullets

        # Capitalize properly
        if title:
            title = title[0].upper() + title[1:]

        return title

    def _calculate_overall_confidence(self, chapters: List[ChapterBoundary]) -> float:
        """Calculate overall confidence for the chapter detection"""
        if not chapters:
            return 0.0

        # Weight chapters by detection method
        weights = {
            'bookmark': 1.0,
            'font_analysis': 0.8,
            'page_pattern': 0.6,
            'ai_analysis': 0.7
        }

        weighted_confidence = 0.0
        total_weight = 0.0

        for chapter in chapters:
            weight = weights.get(chapter.detection_method, 0.5)
            weighted_confidence += chapter.confidence * weight
            total_weight += weight

        return weighted_confidence / total_weight if total_weight > 0 else 0.0

    def _get_used_methods(self, method_lists: List[List[ChapterBoundary]]) -> List[str]:
        """Get list of detection methods that returned results"""
        method_names = ['bookmark', 'font_analysis', 'page_pattern', 'ai_analysis']
        used_methods = []

        for i, method_list in enumerate(method_names):
            if method_lists[i]:
                used_methods.append(method_list[i])

        return used_methods