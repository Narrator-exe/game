const el = {
  simState: document.getElementById('sim-state'),
  simTick: document.getElementById('sim-tick'),
  simModel: document.getElementById('sim-model'),
  simOllama: document.getElementById('sim-ollama'),
  agents: document.getElementById('agents'),
  agentFilter: document.getElementById('agent-filter'),
  detailTitle: document.getElementById('detail-title'),
  detailMeta: document.getElementById('detail-meta'),
  agentDetails: document.getElementById('agent-details'),
  memories: document.getElementById('memories'),
  conversations: document.getElementById('conversations'),
  events: document.getElementById('events'),
  map: document.getElementById('map'),
  askForm: document.getElementById('ask-form'),
  question: document.getElementById('question'),
  qaOutput: document.getElementById('qa-output'),
  runBtn: document.getElementById('btn-run'),
  pauseBtn: document.getElementById('btn-pause'),
  tickBtn: document.getElementById('btn-tick'),
};

const state = {
  agents: [],
  selectedAgentId: null,
  filter: '',
  conversations: [],
};

function safeText(v) {
  return String(v ?? '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
}

function pushEvent(type, text) {
  const item = document.createElement('li');
  item.innerHTML = `<span class="event-type">${safeText(type)}</span>${safeText(text)}`;
  el.events.prepend(item);
  while (el.events.children.length > 80) el.events.lastChild.remove();
}

function renderAgents() {
  el.agents.innerHTML = '';
  const filtered = state.agents.filter((a) => a.name.toLowerCase().includes(state.filter.toLowerCase()));
  filtered.forEach((agent) => {
    const card = document.createElement('div');
    card.className = `agent-card ${state.selectedAgentId === agent.id ? 'active' : ''}`;
    card.innerHTML = `
      <div><strong>${safeText(agent.emoji)} ${safeText(agent.name)}</strong></div>
      <div>${safeText(agent.current_action)}</div>
      <div class="muted">${safeText(agent.location)} · (${agent.x}, ${agent.y})</div>
    `;
    card.onclick = () => {
      state.selectedAgentId = agent.id;
      renderAgents();
      loadAgent(agent.id);
    };
    el.agents.appendChild(card);
  });
}

function renderMap() {
  const map = new Map();
  state.agents.forEach((a) => map.set(`${a.x},${a.y}`, a));
  el.map.innerHTML = '';

  for (let y = 0; y < 10; y++) {
    for (let x = 0; x < 10; x++) {
      const key = `${x},${y}`;
      const cell = document.createElement('div');
      cell.className = 'map-cell';
      if (map.has(key)) {
        const a = map.get(key);
        cell.innerHTML = `<span class="dot" title="${safeText(a.name)}">${safeText(a.emoji || '🙂')}</span>`;
      } else {
        cell.textContent = `${x},${y}`;
      }
      el.map.appendChild(cell);
    }
  }
}

function renderConversations(conversations) {
  el.conversations.innerHTML = '';
  if (!conversations.length) {
    el.conversations.innerHTML = '<li class="muted">No conversations this tick.</li>';
    return;
  }

  conversations.forEach((c) => {
    const li = document.createElement('li');
    const lines = (c.dialog || []).map((d) => `<div><strong>${safeText(d.name)}:</strong> ${safeText(d.dialog)}</div>`).join('');
    li.innerHTML = `<div><strong>${safeText(c.name)}</strong> ↔ <strong>${safeText(c.other)}</strong></div>${lines}`;
    el.conversations.appendChild(li);
  });
}

function renderAgentDetail(agent) {
  el.detailTitle.textContent = `${agent.emoji || '🙂'} ${agent.name}`;
  el.detailMeta.textContent = `${agent.location} · (${agent.x}, ${agent.y})`;
  el.agentDetails.innerHTML = `
    <div class="item"><strong>Current Action:</strong> ${safeText(agent.current_action)}</div>
    <div class="item"><strong>Mood:</strong> ${safeText(agent.mood)}</div>
    <div class="item"><strong>Goals:</strong> ${safeText((agent.goals || []).join(', ') || 'none')}</div>
  `;

  el.memories.innerHTML = '';
  (agent.memories || []).slice().reverse().forEach((m) => {
    const li = document.createElement('li');
    const t = new Date(m.timestamp * 1000).toLocaleTimeString();
    li.innerHTML = `<div>${safeText(m.text)}</div><div class="muted">${t} · ${safeText(m.source)} · importance ${m.importance}</div>`;
    el.memories.appendChild(li);
  });
}

async function loadSimulationState() {
  const res = await fetch('/api/sim');
  const sim = await res.json();
  el.simState.textContent = sim.running ? 'Running' : 'Paused';
  el.simTick.textContent = String(sim.tick);
  el.simModel.textContent = sim.ollama_model;
  el.simOllama.textContent = sim.ollama_available ? 'Connected' : 'Unavailable';
}

async function loadAgents() {
  const res = await fetch('/api/agents');
  state.agents = await res.json();
  renderAgents();
  renderMap();

  if (!state.selectedAgentId && state.agents.length) {
    state.selectedAgentId = state.agents[0].id;
    renderAgents();
    await loadAgent(state.selectedAgentId);
  }
}

async function loadAgent(agentId) {
  const res = await fetch(`/api/agents/${agentId}`);
  if (!res.ok) return;
  const agent = await res.json();
  renderAgentDetail(agent);
}

el.agentFilter.addEventListener('input', () => {
  state.filter = el.agentFilter.value;
  renderAgents();
});

el.askForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = el.question.value.trim();
  if (!question || !state.selectedAgentId) return;

  const res = await fetch(`/api/agents/${state.selectedAgentId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  const data = await res.json();
  el.qaOutput.textContent = `Q: ${question}\nA: ${data.answer || 'No answer.'}`;
  pushEvent('qa', `${state.selectedAgentId}: ${question}`);
  el.question.value = '';
  await loadAgent(state.selectedAgentId);
});

el.runBtn.addEventListener('click', async () => {
  await fetch('/api/sim', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ running: true }),
  });
  await loadSimulationState();
  pushEvent('control', 'Simulation resumed');
});

el.pauseBtn.addEventListener('click', async () => {
  await fetch('/api/sim', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ running: false }),
  });
  await loadSimulationState();
  pushEvent('control', 'Simulation paused');
});

el.tickBtn.addEventListener('click', async () => {
  await fetch('/api/sim/tick', { method: 'POST' });
  await loadSimulationState();
  await loadAgents();
  if (state.selectedAgentId) await loadAgent(state.selectedAgentId);
  pushEvent('control', 'Manual tick requested');
});

function connectEvents() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}/ws/events`);

  ws.onopen = () => pushEvent('system', 'WebSocket connected');

  ws.onmessage = async (event) => {
    const payload = JSON.parse(event.data);

    if (payload.type === 'snapshot') {
      state.agents = payload.agents || [];
      state.conversations = payload.conversations || [];
      renderAgents();
      renderMap();
      renderConversations(state.conversations);
      if (!state.selectedAgentId && state.agents.length) {
        state.selectedAgentId = state.agents[0].id;
      }
      if (state.selectedAgentId) await loadAgent(state.selectedAgentId);
      pushEvent('snapshot', `Received initial world state with ${state.agents.length} agents`);
      return;
    }

    if (payload.type === 'tick') {
      state.agents = payload.agents || state.agents;
      state.conversations = payload.conversations || [];
      renderAgents();
      renderMap();
      renderConversations(state.conversations);
      el.simTick.textContent = String(payload.tick);
      if (state.selectedAgentId) await loadAgent(state.selectedAgentId);
      pushEvent('tick', `Tick ${payload.tick}`);
      return;
    }

    if (payload.type === 'memory') {
      if (state.selectedAgentId === payload.agent_id) await loadAgent(state.selectedAgentId);
      pushEvent('memory', `${payload.agent_id}: ${payload.memory?.text || ''}`);
      return;
    }

    if (payload.type === 'qa') {
      pushEvent('qa', `${payload.agent_id}: ${payload.question}`);
    }
  };

  ws.onclose = () => {
    pushEvent('system', 'WebSocket disconnected; retrying...');
    setTimeout(connectEvents, 1000);
  };
}

(async function init() {
  await loadSimulationState();
  await loadAgents();
  connectEvents();
})();
