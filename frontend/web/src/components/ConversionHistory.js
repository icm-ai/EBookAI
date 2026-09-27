import React, { useState, useEffect } from 'react';

function ConversionHistory({ onSelectFromHistory }) {
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    // Load conversion history from localStorage
    const savedHistory = localStorage.getItem('ebookAI-history');
    if (savedHistory) {
      try {
        setHistory(JSON.parse(savedHistory));
      } catch (error) {
        console.error('Failed to load conversion history:', error);
      }
    }
  }, []);

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem('ebookAI-history');
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatFileSize = (bytes) => {
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  };

  // Expose a stable history writer without capturing stale state.
  React.useEffect(() => {
    const addToHistory = (record) => {
      setHistory((current) => {
        const newHistory = [record, ...current.slice(0, 9)];
        localStorage.setItem('ebookAI-history', JSON.stringify(newHistory));
        return newHistory;
      });
    };

    window.addToConversionHistory = addToHistory;
    return () => {
      if (window.addToConversionHistory === addToHistory) {
        delete window.addToConversionHistory;
      }
    };
  }, []);

  if (history.length === 0) {
    return null;
  }

  return (
    <div className="conversion-history">
      <div className="history-header">
        <button
          className="history-toggle"
          onClick={() => setShowHistory(!showHistory)}
        >
          📝 Conversion History ({history.length})
          <span className="toggle-icon">{showHistory ? '▼' : '▶'}</span>
        </button>
        {history.length > 0 && (
          <button className="clear-history-btn" onClick={clearHistory}>
            🗑️ Clear
          </button>
        )}
      </div>

      {showHistory && (
        <div className="history-content">
          <div className="history-list">
            {history.map((record, index) => (
              <div key={index} className="history-item">
                <div className="history-item-header">
                  <span className="history-filename">
                    📄 {record.originalName}
                  </span>
                  <span className="history-date">
                    {formatDate(record.timestamp)}
                  </span>
                </div>
                <div className="history-details">
                  <span className="history-conversion">
                    {record.fromFormat.toUpperCase()} → {record.toFormat.toUpperCase()}
                  </span>
                  <span className="history-size">
                    {formatFileSize(record.fileSize)}
                  </span>
                  <span className={`history-status ${record.status}`}>
                    {record.status === 'success' ? '✅ Success' : '❌ Failed'}
                  </span>
                </div>
                {record.status === 'success' && record.outputFile && (
                  <div className="history-actions">
                    <button
                      className="history-download-btn"
                      onClick={() => window.open(`/api/download/${record.outputFile}`, '_blank')}
                    >
                      📥 Download
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ConversionHistory;