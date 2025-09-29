import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

function FileUpload({ onFileSelect, selectedFile }) {
  const [uploadError, setUploadError] = useState(null);

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    setUploadError(null);

    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0];
      if (rejection.errors[0].code === 'file-too-large') {
        setUploadError('File too large. Maximum size is 50MB.');
      } else if (rejection.errors[0].code === 'file-invalid-type') {
        setUploadError('Invalid file type. Only EPUB, PDF, TXT, MOBI, and AZW3 files are supported.');
      } else {
        setUploadError('File upload failed. Please try again.');
      }
      return;
    }

    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];

      // Additional validation
      if (file.size === 0) {
        setUploadError('Empty file selected. Please choose a valid file.');
        return;
      }

      if (file.size > 50 * 1024 * 1024) { // 50MB
        setUploadError('File too large. Maximum size is 50MB.');
        return;
      }

      onFileSelect(file);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/epub+zip': ['.epub'],
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/x-mobipocket-ebook': ['.mobi'],
      'application/vnd.amazon.ebook': ['.azw3']
    },
    multiple: false,
    maxSize: 50 * 1024 * 1024 // 50MB
  });

  const clearFile = () => {
    onFileSelect(null);
    setUploadError(null);
  };

  return (
    <div className="file-upload-container">
      <div
        {...getRootProps()}
        className={`upload-area ${isDragActive ? 'dragover' : ''} ${selectedFile ? 'has-file' : ''}`}
      >
        <input {...getInputProps()} />
        {selectedFile ? (
          <div className="file-info">
            <div>
              <p><strong>Selected file:</strong> {selectedFile.name}</p>
              <p>Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
              <p>Type: {selectedFile.type}</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                clearFile();
              }}
              className="clear-file-btn"
            >
              ✕ Clear
            </button>
          </div>
        ) : (
          <div className="upload-prompt">
            {isDragActive ? (
              <p>Drop the file here...</p>
            ) : (
              <div>
                <p>📁 Drag and drop an e-book file here, or click to select</p>
                <p className="supported-formats">Supported formats: EPUB, PDF, TXT, MOBI, AZW3 (max 50MB)</p>
              </div>
            )}
          </div>
        )}
      </div>

      {uploadError && (
        <div className="upload-error">
          ⚠️ {uploadError}
        </div>
      )}
    </div>
  );
}

export default FileUpload;