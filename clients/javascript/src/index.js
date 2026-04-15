export class NpcSimClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async _json(path, opts = {}) {
    const res = await fetch(`${this.baseUrl}${path}`, opts);
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  }

  getSimulation() {
    return this._json('/api/sim');
  }

  setRunning(running) {
    return this._json('/api/sim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ running }),
    });
  }

  listAgents() {
    return this._json('/api/agents');
  }

  getAgent(agentId) {
    return this._json(`/api/agents/${agentId}`);
  }

  getMemories(agentId) {
    return this._json(`/api/agents/${agentId}/memories`);
  }

  askAgent(agentId, question) {
    return this._json(`/api/agents/${agentId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
  }

  connectEvents(onEvent) {
    const wsUrl = this.baseUrl.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsUrl}/ws/events`);
    ws.onmessage = (event) => onEvent(JSON.parse(event.data));
    return ws;
  }
}
