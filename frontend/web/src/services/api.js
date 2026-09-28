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
    requireSignature = false,
    signatureProvider = 'external'
  ) {
    return await api.post(
      `/api/review/sessions/${encodeURIComponent(sessionId)}/release`,
      {
        require_epubcheck: requireEpubcheck,
        require_signature: requireSignature,
        signature_provider: signatureProvider,
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

  // Gold annotation review workbench
  async getGoldReviewQueue() {
    return await api.get('/api/gold-review/queue');
  },

  async createGoldReviewSession(documentId, pageIndex, backend = 'pymupdf') {
    return await api.post('/api/gold-review/sessions', {
      document_id: documentId,
      page_index: pageIndex,
      backend,
    });
  },

  async getGoldReviewSession(sessionId) {
    return await api.get(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}`
    );
  },

  async setGoldReviewTasks(sessionId, tasks) {
    return await api.put(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/tasks`,
      { tasks }
    );
  },

  async upsertGoldReviewElement(sessionId, element) {
    return await api.put(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/elements/${encodeURIComponent(element.id)}`,
      element
    );
  },

  async deleteGoldReviewElement(sessionId, elementId) {
    return await api.delete(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/elements/${encodeURIComponent(elementId)}`
    );
  },

  async setGoldReviewReadingOrder(sessionId, readingOrder) {
    return await api.put(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/reading-order`,
      { reading_order: readingOrder }
    );
  },

  async confirmGoldReviewItem(
    sessionId,
    subject,
    subjectId,
    reviewer,
    note = ''
  ) {
    return await api.post(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/confirm`,
      {
        subject,
        subject_id: subjectId,
        reviewer,
        note,
      }
    );
  },

  async promoteGoldReview(sessionId, reviewer, note = '') {
    return await api.post(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/promote`,
      { reviewer, note }
    );
  },

  async publishGoldReview(sessionId) {
    return await api.post(
      `/api/gold-review/sessions/${encodeURIComponent(sessionId)}/publish`
    );
  },

  getGoldReviewPageUrl(sessionId, scale = 1.5) {
    return `${API_BASE}/api/gold-review/sessions/${encodeURIComponent(sessionId)}/page.png?scale=${encodeURIComponent(scale)}`;
  },

  getGoldReviewExportUrl(sessionId) {
    return `${API_BASE}/api/gold-review/sessions/${encodeURIComponent(sessionId)}/export/promoted`;
  },

  getGoldReviewAuditUrl(sessionId) {
    return `${API_BASE}/api/gold-review/sessions/${encodeURIComponent(sessionId)}/export/audit`;
  },

  async createGoldConsensus(sessionAId, sessionBId) {
    return await api.post('/api/gold-review/consensus', {
      session_a_id: sessionAId,
      session_b_id: sessionBId,
    });
  },

  async getGoldConsensus(bundleId) {
    return await api.get(
      `/api/gold-review/consensus/${encodeURIComponent(bundleId)}`
    );
  },

  async adjudicateGoldConsensus(
    bundleId,
    conflictId,
    choice,
    adjudicator,
    note = ''
  ) {
    return await api.post(
      `/api/gold-review/consensus/${encodeURIComponent(bundleId)}/adjudicate`,
      {
        conflict_id: conflictId,
        choice,
        adjudicator,
        note,
      }
    );
  },

  async publishGoldConsensus(bundleId) {
    return await api.post(
      `/api/gold-review/consensus/${encodeURIComponent(bundleId)}/publish`
    );
  },

  getGoldConsensusExportUrl(bundleId) {
    return `${API_BASE}/api/gold-review/consensus/${encodeURIComponent(bundleId)}/export/gold`;
  },

  getGoldConsensusAuditUrl(bundleId) {
    return `${API_BASE}/api/gold-review/consensus/${encodeURIComponent(bundleId)}/export/audit`;
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