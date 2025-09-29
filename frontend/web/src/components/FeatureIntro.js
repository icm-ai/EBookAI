import React from 'react';

function FeatureIntro() {
  const features = [
    {
      icon: '🔄',
      title: 'Format Conversion',
      description: 'Convert between EPUB, PDF, TXT, MOBI, and AZW3 formats with high quality output'
    },
    {
      icon: '🚀',
      title: 'Fast Processing',
      description: 'Efficient conversion engine with real-time progress tracking'
    },
    {
      icon: '🎯',
      title: 'Easy to Use',
      description: 'Drag & drop interface with instant file preview and validation'
    },
    {
      icon: '📱',
      title: 'Responsive Design',
      description: 'Works perfectly on desktop and mobile devices'
    }
  ];

  return (
    <div className="feature-intro">
      <div className="intro-header">
        <h2>🌟 Key Features</h2>
        <p>Transform your e-books with our powerful conversion platform</p>
      </div>

      <div className="feature-grid">
        {features.map((feature, index) => (
          <div key={index} className="feature-card">
            <div className="feature-icon">{feature.icon}</div>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default FeatureIntro;