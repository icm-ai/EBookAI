import React, { useState, useEffect } from 'react';

function ConversionPanel({ selectedFile, converting, onConvert, result, onDownload }) {
  const [progress, setProgress] = useState(0);

  // Simulate progress during conversion
  useEffect(() => {
    if (converting) {
      setProgress(0);
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 10;
        });
      }, 500);

      return () => clearInterval(interval);
    } else {
      if (result) {
        setProgress(100);
      }
    }
  }, [converting, result]);

  const getTargetFormats = () => {
    if (!selectedFile) return [];

    const fileExt = selectedFile.name.split('.').pop().toLowerCase();

    if (fileExt === 'epub') {
      return [{ format: 'pdf', label: 'PDF', icon: '📄' }];
    } else if (fileExt === 'pdf') {
      return [{ format: 'epub', label: 'EPUB', icon: '📚' }];
    }
    return [];
  };

  const targetFormats = getTargetFormats();

  if (!selectedFile) {
    return (
      <div className="conversion-panel">
        <div className="panel-placeholder">
          <p>📄 Please select a file to start conversion</p>
        </div>
      </div>
    );
  }

  const formatFileSize = (bytes) => {
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  };

  return (
    <div className="conversion-panel">
      <div className="file-preview">
        <h3>📁 File Information</h3>
        <div className="file-details">
          <p><strong>Name:</strong> {selectedFile.name}</p>
          <p><strong>Size:</strong> {formatFileSize(selectedFile.size)}</p>
          <p><strong>Type:</strong> {selectedFile.name.split('.').pop().toUpperCase()}</p>
        </div>
      </div>

      <div className="conversion-options">
        <h3>🔄 Convert to:</h3>

        <div className="format-buttons">
          {targetFormats.map(({ format, label, icon }) => (
            <button
              key={format}
              className={`format-button ${converting ? 'disabled' : ''}`}
              onClick={() => onConvert(format)}
              disabled={converting}
            >
              <span className="format-icon">{icon}</span>
              <span className="format-label">
                {converting ? 'Converting...' : `Convert to ${label}`}
              </span>
            </button>
          ))}
        </div>
      </div>

      {converting && (
        <div className="conversion-progress">
          <h4>🔧 Converting...</h4>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <p className="progress-text">{Math.round(progress)}% complete</p>
        </div>
      )}

      {result && (
        <div className="conversion-result">
          <div className="result-header">
            <h4>✅ Conversion Complete!</h4>
          </div>

          <div className="result-details">
            <p><strong>Status:</strong> <span className="status-success">{result.status}</span></p>
            <p><strong>Output file:</strong> {result.output_file}</p>
            {result.task_id && <p><strong>Task ID:</strong> {result.task_id}</p>}
            {result.message && <p><strong>Message:</strong> {result.message}</p>}
          </div>

          <div className="result-actions">
            <button
              className="download-button"
              onClick={() => onDownload(result.output_file)}
            >
              📥 Download Converted File
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ConversionPanel;