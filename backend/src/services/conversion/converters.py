class FormatConverter:
    """Base class for format converters"""

    def __init__(self):
        pass

    def convert(self, input_path: str, output_path: str, output_format: str):
        """
        Convert file from one format to another

        Args:
            input_path (str): Path to input file
            output_path (str): Path to output file
            output_format (str): Target format

        Returns:
            bool: True if conversion successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement convert method")

class EPUBConverter(FormatConverter):
    """EPUB format converter"""

    def convert(self, input_path: str, output_path: str, output_format: str):
        """Convert EPUB to another format"""
        # Implementation will be added later
        return True

class PDFConverter(FormatConverter):
    """PDF format converter"""

    def convert(self, input_path: str, output_path: str, output_format: str):
        """Convert PDF to another format"""
        # Implementation will be added later
        return True

class MOBIConverter(FormatConverter):
    """MOBI format converter"""

    def convert(self, input_path: str, output_path: str, output_format: str):
        """Convert MOBI to another format"""
        # Implementation will be added later
        return True