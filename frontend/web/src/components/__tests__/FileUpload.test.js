import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import FileUpload from '../FileUpload';

// Mock react-dropzone
jest.mock('react-dropzone', () => ({
  useDropzone: (options) => ({
    getRootProps: () => ({
      'data-testid': 'upload-area',
      onClick: jest.fn(),
    }),
    getInputProps: () => ({
      'data-testid': 'file-input',
      type: 'file',
    }),
    isDragActive: false,
  }),
}));

describe('FileUpload Component', () => {
  const mockOnFileSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders upload area when no file selected', () => {
    render(<FileUpload onFileSelect={mockOnFileSelect} selectedFile={null} />);

    expect(screen.getByTestId('upload-area')).toBeInTheDocument();
    expect(screen.getByText(/drag and drop an e-book file here/i)).toBeInTheDocument();
    expect(screen.getByText(/supported formats: epub, pdf/i)).toBeInTheDocument();
  });

  test('renders file information when file is selected', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 1024 * 1024, // 1MB
      type: 'application/epub+zip',
    };

    render(<FileUpload onFileSelect={mockOnFileSelect} selectedFile={mockFile} />);

    expect(screen.getByText('Selected file:')).toBeInTheDocument();
    expect(screen.getByText('test-book.epub')).toBeInTheDocument();
    expect(screen.getByText('Size: 1.00 MB')).toBeInTheDocument();
    expect(screen.getByText('Type: application/epub+zip')).toBeInTheDocument();
  });

  test('renders clear button when file is selected', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 1024 * 1024,
      type: 'application/epub+zip',
    };

    render(<FileUpload onFileSelect={mockOnFileSelect} selectedFile={mockFile} />);

    const clearButton = screen.getByText('✕ Clear');
    expect(clearButton).toBeInTheDocument();

    fireEvent.click(clearButton);
    expect(mockOnFileSelect).toHaveBeenCalledWith(null);
  });

  test('displays correct file size formatting', () => {
    const testCases = [
      { size: 1024 * 1024, expected: '1.00 MB' },
      { size: 2.5 * 1024 * 1024, expected: '2.50 MB' },
      { size: 512 * 1024, expected: '0.50 MB' },
    ];

    testCases.forEach(({ size, expected }) => {
      const mockFile = {
        name: 'test.epub',
        size,
        type: 'application/epub+zip',
      };

      const { rerender } = render(
        <FileUpload onFileSelect={mockOnFileSelect} selectedFile={mockFile} />
      );

      expect(screen.getByText(`Size: ${expected}`)).toBeInTheDocument();

      rerender(<FileUpload onFileSelect={mockOnFileSelect} selectedFile={null} />);
    });
  });

  test('applies correct CSS classes', () => {
    const { rerender } = render(
      <FileUpload onFileSelect={mockOnFileSelect} selectedFile={null} />
    );

    const uploadArea = screen.getByTestId('upload-area');
    expect(uploadArea).toHaveClass('upload-area');

    const mockFile = {
      name: 'test.epub',
      size: 1024,
      type: 'application/epub+zip',
    };

    rerender(<FileUpload onFileSelect={mockOnFileSelect} selectedFile={mockFile} />);

    expect(uploadArea).toHaveClass('upload-area', 'has-file');
  });
});