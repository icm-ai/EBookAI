import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ConversionPanel from '../ConversionPanel';

// Mock the useEffect timer to avoid async issues
jest.useFakeTimers();

describe('ConversionPanel Component', () => {
  const mockOnConvert = jest.fn();
  const mockOnDownload = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders placeholder when no file selected', () => {
    render(
      <ConversionPanel
        selectedFile={null}
        converting={false}
        onConvert={mockOnConvert}
        result={null}
        onDownload={mockOnDownload}
      />
    );

    expect(screen.getByText(/please select a file to start conversion/i)).toBeInTheDocument();
  });

  test('renders file information when file is selected', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 2 * 1024 * 1024, // 2MB
    };

    render(
      <ConversionPanel
        selectedFile={mockFile}
        converting={false}
        onConvert={mockOnConvert}
        result={null}
        onDownload={mockOnDownload}
      />
    );

    expect(screen.getByText(/file information/i)).toBeInTheDocument();
    expect(screen.getByText('test-book.epub')).toBeInTheDocument();
    expect(screen.getByText('2.00 MB')).toBeInTheDocument();
    expect(screen.getByText('EPUB')).toBeInTheDocument();
  });

  test('renders convert to PDF button for EPUB file', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 1024 * 1024,
    };

    render(
      <ConversionPanel
        selectedFile={mockFile}
        converting={false}
        onConvert={mockOnConvert}
        result={null}
        onDownload={mockOnDownload}
      />
    );

    const convertButton = screen.getByText(/convert to pdf/i);
    expect(convertButton).toBeInTheDocument();
    expect(convertButton).not.toBeDisabled();

    fireEvent.click(convertButton);
    expect(mockOnConvert).toHaveBeenCalledWith('pdf');
  });

  test('renders convert to EPUB button for PDF file', () => {
    const mockFile = {
      name: 'test-document.pdf',
      size: 1024 * 1024,
    };

    render(
      <ConversionPanel
        selectedFile={mockFile}
        converting={false}
        onConvert={mockOnConvert}
        result={null}
        onDownload={mockOnDownload}
      />
    );

    const convertButton = screen.getByText(/convert to epub/i);
    expect(convertButton).toBeInTheDocument();
    expect(convertButton).not.toBeDisabled();

    fireEvent.click(convertButton);
    expect(mockOnConvert).toHaveBeenCalledWith('epub');
  });

  test('shows progress when converting', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 1024 * 1024,
    };

    render(
      <ConversionPanel
        selectedFile={mockFile}
        converting={true}
        onConvert={mockOnConvert}
        result={null}
        onDownload={mockOnDownload}
      />
    );

    expect(screen.getByText(/converting\.\.\./i)).toBeInTheDocument();

    const convertButton = screen.getByText('Converting...');
    expect(convertButton).toBeDisabled();
  });

  test('shows conversion result when completed', () => {
    const mockFile = {
      name: 'test-book.epub',
      size: 1024 * 1024,
    };

    const mockResult = {
      task_id: 'test-task-123',
      status: 'completed',
      output_file: 'test-book_123.pdf',
      message: 'Conversion completed successfully',
    };

    render(
      <ConversionPanel
        selectedFile={mockFile}
        converting={false}
        onConvert={mockOnConvert}
        result={mockResult}
        onDownload={mockOnDownload}
      />
    );

    expect(screen.getByText(/conversion complete/i)).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('test-book_123.pdf')).toBeInTheDocument();
    expect(screen.getByText('test-task-123')).toBeInTheDocument();

    const downloadButton = screen.getByText(/download converted file/i);
    expect(downloadButton).toBeInTheDocument();

    fireEvent.click(downloadButton);
    expect(mockOnDownload).toHaveBeenCalledWith('test-book_123.pdf');
  });

  test('file size formatting works correctly', () => {
    const testCases = [
      { size: 1024 * 1024, expected: '1.00 MB' },
      { size: 2.5 * 1024 * 1024, expected: '2.50 MB' },
      { size: 0.5 * 1024 * 1024, expected: '0.50 MB' },
    ];

    testCases.forEach(({ size, expected }) => {
      const mockFile = {
        name: 'test.epub',
        size,
      };

      const { rerender } = render(
        <ConversionPanel
          selectedFile={mockFile}
          converting={false}
          onConvert={mockOnConvert}
          result={null}
          onDownload={mockOnDownload}
        />
      );

      expect(screen.getByText(expected)).toBeInTheDocument();

      rerender(
        <ConversionPanel
          selectedFile={null}
          converting={false}
          onConvert={mockOnConvert}
          result={null}
          onDownload={mockOnDownload}
        />
      );
    });
  });

  test('handles different file types correctly', () => {
    const fileTypes = [
      { name: 'book.epub', expectedType: 'EPUB', expectedConversion: 'PDF' },
      { name: 'document.pdf', expectedType: 'PDF', expectedConversion: 'EPUB' },
    ];

    fileTypes.forEach(({ name, expectedType, expectedConversion }) => {
      const mockFile = { name, size: 1024 * 1024 };

      const { rerender } = render(
        <ConversionPanel
          selectedFile={mockFile}
          converting={false}
          onConvert={mockOnConvert}
          result={null}
          onDownload={mockOnDownload}
        />
      );

      expect(screen.getByText(expectedType)).toBeInTheDocument();
      expect(screen.getByText(new RegExp(`convert to ${expectedConversion}`, 'i'))).toBeInTheDocument();

      rerender(
        <ConversionPanel
          selectedFile={null}
          converting={false}
          onConvert={mockOnConvert}
          result={null}
          onDownload={mockOnDownload}
        />
      );
    });
  });
});