// Mock the entire API service module
jest.mock('../api', () => ({
  healthCheck: jest.fn(),
  convertFile: jest.fn(),
  downloadFile: jest.fn(),
  listFiles: jest.fn(),
  getStatus: jest.fn(),
  cleanupTask: jest.fn(),
  generateSummary: jest.fn(),
}));

import apiService from '../api';

// Mock DOM methods for file download
Object.defineProperty(window, 'URL', {
  value: {
    createObjectURL: jest.fn(() => 'mock-url'),
    revokeObjectURL: jest.fn(),
  },
});

Object.defineProperty(document, 'createElement', {
  value: jest.fn(() => ({
    href: '',
    setAttribute: jest.fn(),
    click: jest.fn(),
    remove: jest.fn(),
  })),
});

Object.defineProperty(document.body, 'appendChild', {
  value: jest.fn(),
});

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('API service methods exist', () => {
    expect(typeof apiService.healthCheck).toBe('function');
    expect(typeof apiService.convertFile).toBe('function');
    expect(typeof apiService.downloadFile).toBe('function');
    expect(typeof apiService.listFiles).toBe('function');
    expect(typeof apiService.getStatus).toBe('function');
    expect(typeof apiService.cleanupTask).toBe('function');
    expect(typeof apiService.generateSummary).toBe('function');
  });

  test('healthCheck can be called', async () => {
    const mockResponse = { status: 'healthy' };
    apiService.healthCheck.mockResolvedValue(mockResponse);

    const result = await apiService.healthCheck();
    expect(result).toEqual(mockResponse);
    expect(apiService.healthCheck).toHaveBeenCalled();
  });

  test('convertFile can be called with parameters', async () => {
    const mockFile = { name: 'test.epub' };
    const mockResponse = { task_id: 'test-123' };
    apiService.convertFile.mockResolvedValue(mockResponse);

    const result = await apiService.convertFile(mockFile, 'pdf');
    expect(result).toEqual(mockResponse);
    expect(apiService.convertFile).toHaveBeenCalledWith(mockFile, 'pdf');
  });

  test('getStatus can be called with task ID', async () => {
    const taskId = 'test-123';
    const mockResponse = { task_id: taskId, status: 'completed' };
    apiService.getStatus.mockResolvedValue(mockResponse);

    const result = await apiService.getStatus(taskId);
    expect(result).toEqual(mockResponse);
    expect(apiService.getStatus).toHaveBeenCalledWith(taskId);
  });
});