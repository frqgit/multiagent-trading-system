// ── WebSocket client with auto-reconnect ──

export class WebSocketClient {
  constructor(path) {
    this._ws = null;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this._url = `${proto}//${location.host}${path}`;
    this._handlers = new Map();
    this._reconnectTimer = null;
    this._reconnectDelay = 1000;
    this._maxReconnectDelay = 30000;
    this._shouldReconnect = true;
  }

  connect() {
    if (this._ws?.readyState === WebSocket.OPEN) return;

    this._ws = new WebSocket(this._url);

    this._ws.onopen = () => {
      this._reconnectDelay = 1000;
      this._emit('_connected', {});
    };

    this._ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const type = data.type;
        if (type) this._emit(type, data);
        this._emit('_message', data);
      } catch {
        // skip non-JSON messages
      }
    };

    this._ws.onclose = () => {
      this._emit('_disconnected', {});
      if (this._shouldReconnect) {
        this._reconnectTimer = setTimeout(() => {
          this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
          this.connect();
        }, this._reconnectDelay);
      }
    };

    this._ws.onerror = () => {
      this._ws?.close();
    };
  }

  disconnect() {
    this._shouldReconnect = false;
    if (this._reconnectTimer) clearTimeout(this._reconnectTimer);
    this._ws?.close();
    this._ws = null;
  }

  send(data) {
    if (this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(data));
    }
  }

  on(type, handler) {
    if (!this._handlers.has(type)) this._handlers.set(type, new Set());
    this._handlers.get(type).add(handler);
    return () => this._handlers.get(type)?.delete(handler);
  }

  _emit(type, data) {
    this._handlers.get(type)?.forEach(fn => fn(data));
  }

  get connected() {
    return this._ws?.readyState === WebSocket.OPEN;
  }
}

// ── Singleton instances ──
export const marketWS = new WebSocketClient('/ws/market');
export const signalsWS = new WebSocketClient('/ws/signals');
export const portfolioWS = new WebSocketClient('/ws/portfolio');
