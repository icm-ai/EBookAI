import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ConversionPanel from './components/ConversionPanel';
import api from './services/api';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [converting, setConverting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileSelect = (file) => {
    setSelectedFile(file);
    setResult(null);
    setError(null);
  };

  const handleConvert = async (targetFormat) => {
    if (!selectedFile) return;

    setConverting(true);
    setError(null);

    try {
      const response = await api.convertFile(selectedFile, targetFormat);
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Conversion failed');
    } finally {
      setConverting(false);
    }
  };

  const handleDownload = async (filename) => {
    try {
      await api.downloadFile(filename);
    } catch (err) {
      setError('Download failed');
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>EBookAI</h1>
        <p>AI-enhanced e-book processing platform</p>
      </div>

      <FileUpload
        onFileSelect={handleFileSelect}
        selectedFile={selectedFile}
      />

      <ConversionPanel
        selectedFile={selectedFile}
        converting={converting}
        onConvert={handleConvert}
        result={result}
        onDownload={handleDownload}
      />

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}
    </div>
  );
}

export default App;