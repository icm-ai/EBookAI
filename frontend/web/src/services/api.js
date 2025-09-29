import axios from 'axios';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'http://localhost:8000'
  : 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes for conversion
});

const apiService = {
  // Health check
  async healthCheck() {
    return await api.get('/health');
  },

  // File operations
  async convertFile(file, targetFormat) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_format', targetFormat);

    return await api.post('/convert', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  async downloadFile(filename) {
    const response = await api.get(`/download/${filename}`, {
      responseType: 'blob',
    });

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);

    return response;
  },

  async listFiles(fileType = 'output') {
    return await api.get(`/files?file_type=${fileType}`);
  },

  // Task status and management
  async getStatus(taskId) {
    return await api.get(`/status/${taskId}`);
  },

  async cleanupTask(taskId) {
    return await api.delete(`/cleanup/${taskId}`);
  },

  // AI operations
  async generateSummary(text, maxLength = 300) {
    return await api.post('/ai/summary', {
      text,
      max_length: maxLength,
    });
  },
};

export default apiService;