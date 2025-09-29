class FormatValidator:
    """Base class for format validators"""

    def __init__(self):
        pass

    def validate(self, file_path: str):
        """
        Validate file format

        Args:
            file_path (str): Path to file to validate

        Returns:
            bool: True if file format is valid, False otherwise
        """
        raise NotImplementedError("Subclasses must implement validate method")


class EPUBValidator(FormatValidator):
    """EPUB format validator"""

    def validate(self, file_path: str):
        """Validate EPUB file"""
        # Implementation will be added later
        return True


class PDFValidator(FormatValidator):
    """PDF format validator"""

    def validate(self, file_path: str):
        """Validate PDF file"""
        # Implementation will be added later
        return True


class MOBIValidator(FormatValidator):
    """MOBI format validator"""

    def validate(self, file_path: str):
        """Validate MOBI file"""
        # Implementation will be added later
        return True
