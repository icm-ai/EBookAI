/**
 * Error boundary component to catch and display React errors gracefully.
 */
import React from 'react';
import '../styles/ErrorBoundary.css';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    this.setState({
      error,
      errorInfo
    });

    // Log to error tracking service
    if (window.logError) {
      window.logError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-content">
            <div className="error-icon">⚠️</div>
            <h1>Oops! Something went wrong</h1>
            <p className="error-message">
              The application encountered an unexpected error. Don't worry, your files are safe.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="error-details">
                <summary>Technical details (development mode)</summary>
                <pre className="error-stack">
                  {this.state.error.toString()}
                  {'\n\n'}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <div className="error-actions">
              <button className="error-btn primary" onClick={this.handleReset}>
                Try Again
              </button>
              <button className="error-btn secondary" onClick={this.handleReload}>
                Reload Page
              </button>
            </div>

            <div className="error-help">
              <p>If the problem persists:</p>
              <ul>
                <li>Clear your browser cache</li>
                <li>Try a different browser</li>
                <li>Report the issue on GitHub</li>
              </ul>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
