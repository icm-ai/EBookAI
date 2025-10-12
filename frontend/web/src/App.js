import React, { useState, useEffect } from 'react';
import FileUpload from './components/FileUpload';
import ConversionPanel from './components/ConversionPanel';
import FeatureIntro from './components/FeatureIntro';
import ConversionHistory from './components/ConversionHistory';
import BatchUpload from './components/BatchUpload';
import api from './services/api';
import websocketService from './services/websocket';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [converting, setConverting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const [activeTab, setActiveTab] = useState('single'); // 'single' or 'batch'

  useEffect(() => {
    // Initialize WebSocket connection
    websocketService.connect().catch(console.error);

    return () => {
      websocketService.disconnect();
    };
  }, []);

  const handleFileSelect = (file) => {
    setSelectedFile(file);
    setResult(null);
    setError(null);
    setProgressData(null);
  };

  const handleConvert = async (targetFormat) => {
    if (!selectedFile) return;

    setConverting(true);
    setError(null);
    setProgressData(null);

    try {
      const response = await api.convertFile(selectedFile, targetFormat);
      const taskId = response.data.task_id;

      // Subscribe to progress updates
      websocketService.subscribeToProgress(taskId, (progress) => {
        setProgressData(progress);

        if (progress.status === 'completed') {
          setResult(response.data);
          setConverting(false);
          websocketService.unsubscribeFromProgress(taskId);

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
        } else if (progress.status === 'failed') {
          setError(progress.error_message || 'Conversion failed');
          setConverting(false);
          websocketService.unsubscribeFromProgress(taskId);

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
        }
      });

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
      setConverting(false);

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
    }
  };

  const handleBatchConvert = async (files, targetFormat) => {
    setConverting(true);
    setError(null);
    setProgressData(null);

    try {
      const response = await api.batchConvertFiles(files, targetFormat);
      const batchId = response.data.batch_id;

      // Subscribe to batch progress updates
      websocketService.subscribeToProgress(batchId, (progress) => {
        setProgressData(progress);

        if (progress.status === 'completed' || progress.status === 'completed_with_errors') {
          setConverting(false);
          websocketService.unsubscribeFromProgress(batchId);

          // Add batch results to history
          if (window.addToConversionHistory) {
            const historyRecord = {
              originalName: `Batch conversion (${files.length} files)`,
              fromFormat: 'batch',
              toFormat: targetFormat,
              fileSize: files.reduce((total, file) => total + file.size, 0),
              status: progress.status === 'completed' ? 'success' : 'partial',
              timestamp: Date.now()
            };
            window.addToConversionHistory(historyRecord);
          }
        } else if (progress.status === 'failed') {
          setError('Batch conversion failed');
          setConverting(false);
          websocketService.unsubscribeFromProgress(batchId);
        }
      });

    } catch (err) {
      let errorMessage = 'Batch conversion failed';
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
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

      {!selectedFile && !result && activeTab === 'single' && (
        <FeatureIntro />
      )}

      <div className="conversion-tabs">
        <button
          className={`tab-button ${activeTab === 'single' ? 'active' : ''}`}
          onClick={() => setActiveTab('single')}
        >
          📄 Single File
        </button>
        <button
          className={`tab-button ${activeTab === 'batch' ? 'active' : ''}`}
          onClick={() => setActiveTab('batch')}
        >
          📚 Batch Conversion
        </button>
      </div>

      {activeTab === 'single' ? (
        <>
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
            progressData={progressData}
          />
        </>
      ) : (
        <BatchUpload
          onBatchConvert={handleBatchConvert}
        />
      )}

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