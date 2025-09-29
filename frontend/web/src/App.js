import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ConversionPanel from './components/ConversionPanel';
import FeatureIntro from './components/FeatureIntro';
import ConversionHistory from './components/ConversionHistory';
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

      // Add to conversion history
      if (window.addToConversionHistory) {
        const historyRecord = {
          originalName: selectedFile.name,
          fromFormat: selectedFile.name.split('.').pop().toLowerCase(),
          toFormat: targetFormat,
          fileSize: selectedFile.size,
          status: 'success',
          outputFile: response.data.output_file,
          timestamp: Date.now()
        };
        window.addToConversionHistory(historyRecord);
      }
    } catch (err) {
      // Enhanced error handling with Chinese messages
      let errorMessage = 'Conversion failed';
      if (err.response?.data?.user_message) {
        errorMessage = err.response.data.user_message;
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);

      // Add failed conversion to history
      if (window.addToConversionHistory) {
        const historyRecord = {
          originalName: selectedFile.name,
          fromFormat: selectedFile.name.split('.').pop().toLowerCase(),
          toFormat: targetFormat,
          fileSize: selectedFile.size,
          status: 'failed',
          timestamp: Date.now()
        };
        window.addToConversionHistory(historyRecord);
      }
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

      {!selectedFile && !result && (
        <FeatureIntro />
      )}

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

      <ConversionHistory />
    </div>
  );
}

export default App;