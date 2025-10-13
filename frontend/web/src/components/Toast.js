/**
 * Toast notification component for user feedback.
 * Displays temporary messages for success, error, warning, and info.
 */
import React, { useState, useEffect } from 'react';
import '../styles/Toast.css';

function Toast({ message, type = 'info', duration = 5000, onClose }) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      if (onClose) {
        setTimeout(onClose, 300); // Wait for animation
      }
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    if (onClose) {
      setTimeout(onClose, 300);
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✕';
      case 'warning':
        return '⚠';
      case 'info':
      default:
        return 'ⓘ';
    }
  };

  const getClassName = () => {
    let className = 'toast';
    if (!isVisible) className += ' toast-exit';
    className += ` toast-${type}`;
    return className;
  };

  return (
    <div className={getClassName()}>
      <div className="toast-icon">{getIcon()}</div>
      <div className="toast-message">{message}</div>
      <button className="toast-close" onClick={handleClose}>×</button>
    </div>
  );
}

export default Toast;
