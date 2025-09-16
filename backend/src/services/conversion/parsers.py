class DocumentParser:
    """Base class for document parsers"""

    def __init__(self):
        pass

    def parse(self, file_path: str):
        """
        Parse document file

        Args:
            file_path (str): Path to document file

        Returns:
            dict: Parsed document data
        """
        raise NotImplementedError("Subclasses must implement parse method")

class EPUBParser(DocumentParser):
    """EPUB document parser"""

    def parse(self, file_path: str):
        """Parse EPUB file"""
        # Implementation will be added later
        return {}

class PDFParser(DocumentParser):
    """PDF document parser"""

    def parse(self, file_path: str):
        """Parse PDF file"""
        # Implementation will be added later
        return {}

class MOBIParser(DocumentParser):
    """MOBI document parser"""

    def parse(self, file_path: str):
        """Parse MOBI file"""
        # Implementation will be added later
        return {}