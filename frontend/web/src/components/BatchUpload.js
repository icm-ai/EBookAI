import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

function BatchUpload({ onBatchConvert }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadError, setUploadError] = useState(null);
  const [targetFormat, setTargetFormat] = useState('pdf');

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    setUploadError(null);

    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0];
      if (rejection.errors[0].code === 'file-too-large') {
        setUploadError('Some files are too large. Maximum size is 50MB per file.');
      } else if (rejection.errors[0].code === 'file-invalid-type') {
        setUploadError('Invalid file type. Only EPUB, PDF, TXT, MOBI, and AZW3 files are supported.');
      } else {
        setUploadError('Some files could not be uploaded. Please try again.');
      }
      return;
    }

    if (acceptedFiles.length > 0) {
      // Validate total file count
      const totalFiles = selectedFiles.length + acceptedFiles.length;
      if (totalFiles > 50) {
        setUploadError('Too many files. Maximum 50 files allowed per batch.');
        return;
      }

      // Add new files to the list
      const newFiles = acceptedFiles.map(file => ({
        file,
        id: `${file.name}-${Date.now()}-${Math.random()}`,
        status: 'ready'
      }));

      setSelectedFiles(prev => [...prev, ...newFiles]);
    }
  }, [selectedFiles]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/epub+zip': ['.epub'],
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/x-mobipocket-ebook': ['.mobi'],
      'application/vnd.amazon.ebook': ['.azw3']
    },
    multiple: true,
    maxSize: 50 * 1024 * 1024 // 50MB
  });

  const removeFile = (fileId) => {
    setSelectedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const clearAllFiles = () => {
    setSelectedFiles([]);
    setUploadError(null);
  };

  const handleBatchConvert = () => {
    if (selectedFiles.length === 0) {
      setUploadError('Please select at least one file.');
      return;
    }

    const files = selectedFiles.map(f => f.file);
    onBatchConvert(files, targetFormat);
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getTotalSize = () => {
    return selectedFiles.reduce((total, file) => total + file.file.size, 0);
  };

  return (
    <div className="batch-upload-container">
      <div className="batch-upload-header">
        <h3>📚 Batch File Conversion</h3>
        <p>Upload multiple files and convert them all at once</p>
      </div>

      <div
        {...getRootProps()}
        className={`batch-upload-area ${isDragActive ? 'dragover' : ''} ${selectedFiles.length > 0 ? 'has-files' : ''}`}
      >
        <input {...getInputProps()} />
        {selectedFiles.length === 0 ? (
          <div className="upload-prompt">
            {isDragActive ? (
              <p>Drop the files here...</p>
            ) : (
              <div>
                <p>📁 Drag and drop multiple e-book files here, or click to select</p>
                <p className="supported-formats">Supported formats: EPUB, PDF, TXT, MOBI, AZW3</p>
                <p className="batch-limits">Maximum: 50 files, 50MB per file</p>
              </div>
            )}
          </div>
        ) : (
          <div className="batch-summary">
            <div className="summary-stats">
              <span className="file-count">{selectedFiles.length} files selected</span>
              <span className="total-size">Total size: {formatFileSize(getTotalSize())}</span>
            </div>
            <p className="add-more-hint">Drop more files here or click to add more</p>
          </div>
        )}
      </div>

      {selectedFiles.length > 0 && (
        <div className="batch-file-list">
          <div className="file-list-header">
            <span>Selected Files</span>
            <button className="clear-all-btn" onClick={clearAllFiles}>
              🗑️ Clear All
            </button>
          </div>

          <div className="file-list">
            {selectedFiles.map((fileItem) => (
              <div key={fileItem.id} className="batch-file-item">
                <div className="file-info">
                  <span className="file-name">📄 {fileItem.file.name}</span>
                  <span className="file-size">{formatFileSize(fileItem.file.size)}</span>
                </div>
                <button
                  className="remove-file-btn"
                  onClick={() => removeFile(fileItem.id)}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedFiles.length > 0 && (
        <div className="batch-controls">
          <div className="format-selection">
            <label htmlFor="batch-target-format">Convert all to:</label>
            <select
              id="batch-target-format"
              value={targetFormat}
              onChange={(e) => setTargetFormat(e.target.value)}
              className="format-select"
            >
              <option value="pdf">PDF</option>
              <option value="epub">EPUB</option>
              <option value="txt">TXT</option>
              <option value="mobi">MOBI</option>
              <option value="azw3">AZW3</option>
            </select>
          </div>

          <button
            className="batch-convert-btn"
            onClick={handleBatchConvert}
            disabled={selectedFiles.length === 0}
          >
            🚀 Start Batch Conversion ({selectedFiles.length} files)
          </button>
        </div>
      )}

      {uploadError && (
        <div className="upload-error">
          ⚠️ {uploadError}
        </div>
      )}
    </div>
  );
}

export default BatchUpload;