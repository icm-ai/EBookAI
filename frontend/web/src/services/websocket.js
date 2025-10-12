class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.progressCallbacks = new Map();
    this.connectionCallbacks = [];
    this.isConnecting = false;
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    if (this.isConnecting) {
      return new Promise((resolve) => {
        this.connectionCallbacks.push(resolve);
      });
    }

    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      try {
        const wsUrl = process.env.NODE_ENV === 'production'
          ? 'wss://localhost:8000/ws/progress'
          : 'ws://localhost:8000/ws/progress';

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.isConnecting = false;

          // Send ping to test connection
          this.send({ type: 'ping' });

          resolve();
          this.connectionCallbacks.forEach(callback => callback());
          this.connectionCallbacks = [];
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.isConnecting = false;

          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
              this.reconnectAttempts++;
              console.log(`Reconnection attempt ${this.reconnectAttempts}`);
              this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnecting = false;
          reject(error);
        };

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  handleMessage(data) {
    switch (data.type) {
      case 'progress_update':
        const callback = this.progressCallbacks.get(data.task_id);
        if (callback) {
          callback(data.data);
        }
        break;
      case 'pong':
        // Connection test successful
        break;
      default:
        console.log('Unknown WebSocket message type:', data.type);
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  subscribeToProgress(taskId, callback) {
    this.progressCallbacks.set(taskId, callback);

    // Subscribe to task progress
    this.send({
      type: 'subscribe',
      task_id: taskId
    });
  }

  unsubscribeFromProgress(taskId) {
    this.progressCallbacks.delete(taskId);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}

// Export a singleton instance
export const websocketService = new WebSocketService();
export default websocketService;