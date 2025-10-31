"""
Layout Analyzer Module - Advanced layout analysis using pdfplumber

This module provides sophisticated layout analysis for PDF documents including:
- Multi-column layout detection
- Reading order analysis
- Table structure identification
- Content region analysis
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import pdfplumber
from utils.logging_config import get_logger


@dataclass
class TextRegion:
    """Represents a region of text with layout information"""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float
    page_num: int
    region_type: str  # 'text', 'heading', 'table', 'image_caption'
    reading_order: int
    column_number: Optional[int] = None


@dataclass
class ColumnInfo:
    """Information about detected columns"""
    column_number: int
    x_start: float
    x_end: float
    width: float
    text_regions: List[TextRegion]


@dataclass
class TableInfo:
    """Information about detected tables"""
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    rows: int
    columns: int
    cells: List[List[str]]


class LayoutAnalyzer:
    """Advanced layout analyzer using pdfplumber for precise layout detection"""

    def __init__(self):
        self.logger = get_logger("layout_analyzer")

    def analyze_page_layout(self, page: pdfplumber.Page, page_num: int) -> Tuple[List[ColumnInfo], List[TextRegion], List[TableInfo]]:
        """
        Analyze page layout and detect columns, text regions, and tables

        Args:
            page: pdfplumber Page object
            page_num: Page number for reference

        Returns:
            Tuple of (columns, text_regions, tables)
        """
        try:
            self.logger.debug(f"Analyzing layout for page {page_num}")

            # Extract words with precise positions
            words = page.extract_words(x_tolerance=1, y_tolerance=1)

            if not words:
                return [], [], []

            # Detect columns
            columns = self._detect_columns(words)

            # Group text into regions
            text_regions = self._group_text_regions(page, words, columns)

            # Detect tables
            tables = self._detect_tables(page, page_num)

            self.logger.debug(f"Page {page_num}: {len(columns)} columns, {len(text_regions)} regions, {len(tables)} tables")
            return columns, text_regions, tables

        except Exception as e:
            self.logger.error(f"Layout analysis failed for page {page_num}: {str(e)}")
            return [], [], []

    def _detect_columns(self, words: List[Dict]) -> List[ColumnInfo]:
        """Detect column structure based on word positions"""
        if not words:
            return []

        # Analyze x-coordinate distribution
        x_coords = [word['x0'] for word in words]
        x_coords.sort()

        # Find column boundaries using gaps in text
        min_gap = 20  # Minimum gap between columns (in points)
        column_boundaries = []

        current_x = x_coords[0]
        column_start = current_x

        for i in range(1, len(x_coords)):
            if x_coords[i] - current_x > min_gap:
                # Found a column boundary
                column_end = current_x
                column_boundaries.append((column_start, column_end))
                column_start = x_coords[i]
            current_x = x_coords[i]

        # Add last column
        column_boundaries.append((column_start, x_coords[-1]))

        # Create ColumnInfo objects
        columns = []
        for i, (x_start, x_end) in enumerate(column_boundaries):
            # Find the furthest x coordinate in this column
            column_words = [w for w in words if x_start <= w['x0'] <= x_end]
            if column_words:
                actual_x_end = max(w['x1'] for w in column_words)
            else:
                actual_x_end = x_end

            column_info = ColumnInfo(
                column_number=i,
                x_start=x_start,
                x_end=actual_x_end,
                width=actual_x_end - x_start,
                text_regions=[]
            )
            columns.append(column_info)

        return columns

    def _group_text_regions(self, page: pdfplumber.Page, words: List[Dict], columns: List[ColumnInfo]) -> List[TextRegion]:
        """Group words into text regions and assign to columns"""
        text_regions = []

        if not words:
            return text_regions

        # Sort words by reading order (top to bottom, left to right)
        words.sort(key=lambda w: (w['top'], w['left']))

        # Group consecutive words into lines and regions
        current_line_words = []
        current_top = words[0]['top']
        line_tolerance = 5  # Tolerance for line grouping

        for word in words:
            if abs(word['top'] - current_top) > line_tolerance:
                # New line, process previous line
                if current_line_words:
                    line_regions = self._process_line(page, current_line_words, columns)
                    text_regions.extend(line_regions)
                current_line_words = [word]
                current_top = word['top']
            else:
                current_line_words.append(word)

        # Process last line
        if current_line_words:
            line_regions = self._process_line(page, current_line_words, columns)
            text_regions.extend(line_regions)

        # Assign reading order
        for i, region in enumerate(text_regions):
            region.reading_order = i

        return text_regions

    def _process_line(self, page: pdfplumber.Page, line_words: List[Dict], columns: List[ColumnInfo]) -> List[TextRegion]:
        """Process a line of words and create text regions"""
        if not line_words:
            return []

        # Sort words by x position
        line_words.sort(key=lambda w: w['left'])

        # Group words by column
        column_groups = {}
        for word in line_words:
            for col in columns:
                if col.x_start <= word['x0'] <= col.x_end:
                    if col.column_number not in column_groups:
                        column_groups[col.column_number] = []
                    column_groups[col.column_number].append(word)
                    break

        # Create text regions for each column
        regions = []
        for col_num, col_words in column_groups.items():
            if col_words:
                # Combine words into text
                text = ' '.join(word['text'] for word in col_words)

                # Calculate bounding box
                x0 = min(word['x0'] for word in col_words)
                y0 = min(word['top'] for word in col_words)
                x1 = max(word['x1'] for word in col_words)
                y1 = max(word['bottom'] for word in col_words)

                # Determine region type
                region_type = self._classify_region_type(col_words)

                region = TextRegion(
                    text=text,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    width=x1 - x0,
                    height=y1 - y0,
                    page_num=page.page_number,
                    region_type=region_type,
                    reading_order=0,  # Will be set later
                    column_number=col_num
                )
                regions.append(region)

        return regions

    def _classify_region_type(self, words: List[Dict]) -> str:
        """Classify the type of text region based on font characteristics"""
        if not words:
            return 'text'

        # Check for heading characteristics
        avg_font_size = sum(word.get('size', 12) for word in words) / len(words)

        # Larger text might be a heading
        if avg_font_size > 14:
            return 'heading'

        # Check for table-like structure (multiple aligned words)
        if len(words) > 3 and self._has_tabular_structure(words):
            return 'table'

        # Default to text
        return 'text'

    def _has_tabular_structure(self, words: List[Dict]) -> bool:
        """Check if words have tabular structure (aligned columns)"""
        if len(words) < 3:
            return False

        # Check for regular spacing between words
        positions = [word['x0'] for word in words]
        positions.sort()

        # Look for at least 2 regular gaps
        gaps = []
        for i in range(1, len(positions)):
            gaps.append(positions[i] - positions[i-1])

        # Check if gaps are somewhat regular
        if len(gaps) >= 2:
            avg_gap = sum(gaps) / len(gaps)
            variance = sum((gap - avg_gap) ** 2 for gap in gaps) / len(gaps)
            std_dev = variance ** 0.5

            # If standard deviation is small relative to gap size, likely tabular
            if std_dev < avg_gap * 0.3:
                return True

        return False

    def _detect_tables(self, page: pdfplumber.Page, page_num: int) -> List[TableInfo]:
        """Detect tables in the page"""
        tables = []

        try:
            # Use pdfplumber's table detection
            tables_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "explicit_vertical_lines": page.curves + page.edges,
                "explicit_horizontal_lines": page.curves + page.edges,
            }

            detected_tables = page.find_tables(tables_settings)

            for table in detected_tables:
                try:
                    # Extract table data
                    table_data = table.extract()

                    # Filter out empty rows
                    valid_rows = [row for row in table_data if any(cell and cell.strip() for cell in row)]

                    if len(valid_rows) >= 2:  # At least 2 rows to be a table
                        table_info = TableInfo(
                            page_num=page_num,
                            x0=table.bbox[0],
                            y0=table.bbox[1],
                            x1=table.bbox[2],
                            y1=table.bbox[3],
                            rows=len(valid_rows),
                            columns=len(valid_rows[0]) if valid_rows else 0,
                            cells=valid_rows
                        )
                        tables.append(table_info)

                except Exception as e:
                    self.logger.warning(f"Failed to extract table data: {str(e)}")
                    continue

        except Exception as e:
            self.logger.warning(f"Table detection failed for page {page_num}: {str(e)}")

        return tables

    def get_reading_order(self, text_regions: List[TextRegion], columns: List[ColumnInfo]) -> List[TextRegion]:
        """
        Determine the correct reading order for text regions

        Args:
            text_regions: List of text regions
            columns: Detected columns

        Returns:
            Text regions sorted in correct reading order
        """
        if not text_regions:
            return text_regions

        if len(columns) <= 1:
            # Single column - sort by y position
            return sorted(text_regions, key=lambda r: (r.y0, r.x0))

        # Multi-column - determine column order first, then sort within columns
        sorted_regions = []

        # Sort columns by x position
        sorted_columns = sorted(columns, key=lambda c: c.x_start)

        # Process each column
        for col in sorted_columns:
            # Get regions in this column
            col_regions = [r for r in text_regions if r.column_number == col.column_number]

            # Sort regions within column by y position
            col_regions.sort(key=lambda r: r.y0)

            # Add to final list
            sorted_regions.extend(col_regions)

        # Update reading order numbers
        for i, region in enumerate(sorted_regions):
            region.reading_order = i

        return sorted_regions

    def analyze_document_structure(self, pages: List[pdfplumber.Page]) -> Dict[str, Any]:
        """
        Analyze overall document structure across all pages

        Args:
            pages: List of pdfplumber Page objects

        Returns:
            Dictionary with document structure analysis
        """
        structure_analysis = {
            'total_pages': len(pages),
            'multi_column_pages': 0,
            'single_column_pages': 0,
            'pages_with_tables': 0,
            'total_tables': 0,
            'average_columns_per_page': 0,
            'column_consistency': True
        }

        all_column_counts = []

        for page_num, page in enumerate(pages):
            columns, text_regions, tables = self.analyze_page_layout(page, page_num)

            column_count = len(columns)
            all_column_counts.append(column_count)

            if column_count > 1:
                structure_analysis['multi_column_pages'] += 1
            else:
                structure_analysis['single_column_pages'] += 1

            if tables:
                structure_analysis['pages_with_tables'] += 1
                structure_analysis['total_tables'] += len(tables)

        # Calculate statistics
        if all_column_counts:
            structure_analysis['average_columns_per_page'] = sum(all_column_counts) / len(all_column_counts)

            # Check column consistency
            unique_counts = set(all_column_counts)
            structure_analysis['column_consistency'] = len(unique_counts) <= 2

        return structure_analysis