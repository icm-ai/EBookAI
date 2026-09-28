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

  // Human review operations
  async getReviewAIProviders() {
    return await api.get('/api/review/ai-providers');
  },

  async createReviewSession(file) {
    const formData = new FormData();
    formData.append('file', file);

    return await api.post('/api/review/sessions', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  async getReviewSession(sessionId) {
    return await api.get(
      `/api/review/sessions/${encodeURIComponent(sessionId)}`
    );
  },

  async acceptReviewIssue(sessionId, issueId) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/issues/${encodeURIComponent(issueId)}/accept`
    );
  },

  async rejectReviewIssue(sessionId, issueId, reason = '') {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/issues/${encodeURIComponent(issueId)}/reject`,
      { reason }
    );
  },

  async generateAIRepairProposal(
    sessionId,
    issueId,
    provider = null,
    includeSourceImages = false
  ) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/issues/${encodeURIComponent(issueId)}/ai-proposals`,
      {
        provider,
        include_source_images: includeSourceImages,
      }
    );
  },

  async acceptAIRepairProposal(sessionId, proposalId) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/ai-proposals/${encodeURIComponent(proposalId)}/accept`
    );
  },

  async rejectAIRepairProposal(sessionId, proposalId) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/ai-proposals/${encodeURIComponent(proposalId)}/reject`
    );
  },

  async undoReviewPatch(sessionId, patchId) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/patches/${encodeURIComponent(patchId)}/undo`
    );
  },

  async runReviewPublicationQA(sessionId) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/publication-qa`
    );
  },

  async buildReviewRelease(
    sessionId,
    requireEpubcheck = false,
    requireSignature = false
  ) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/release`,
      {
        require_epubcheck: requireEpubcheck,
        require_signature: requireSignature,
      }
    );
  },

  async verifyReviewRelease(sessionId) {
    return await api.get(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/release/verify`
    );
  },

  getReviewSourceUrl(sessionId) {
    return `${API_BASE}/api/review/sessions/${encodeURIComponent(sessionId)}/source`;
  },

  getReviewExportUrl(sessionId, format) {
    return `${API_BASE}/api/review/sessions/${encodeURIComponent(sessionId)}/export/${format}`;
  },

  // Batch operations
  async batchConvertFiles(files, targetFormat) {
    const formData = new FormData();
    formData.append('target_format', targetFormat);

    files.forEach(file => {
      formData.append('files', file);
    });

    return await api.post('/batch/convert', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  async getBatchStatus(batchId) {
    return await api.get(`/batch/status/${batchId}`);
  },
};

export default apiService;