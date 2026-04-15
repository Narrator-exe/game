const agentsNode = document.getElementById('agents');
const detailsNode = document.getElementById('agent-details');
const detailTitle = document.getElementById('detail-title');
const memoriesNode = document.getElementById('memories');
const askForm = document.getElementById('ask-form');
const questionNode = document.getElementById('question');
const qaOutput = document.getElementById('qa-output');
const statusNode = document.getElementById('sim-status');

const state = {
  selectedAgentId: null,
  agents: [],
};

function fmt(ts) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function renderAgents() {
  agentsNode.innerHTML = '';
  state.agents.forEach((agent) => {
    const card = document.createElement('div');
    card.className = `agent-card ${state.selectedAgentId === agent.id ? 'active' : ''}`;
    card.innerHTML = `
      <strong>${agent.name}</strong>
      <div>${agent.current_action}</div>
      <div class="meta">Mood: ${agent.mood} · Pos: (${agent.x}, ${agent.y})</div>
    `;
    card.onclick = () => {
      state.selectedAgentId = agent.id;
      renderAgents();
      loadAgent(agent.id);
    };
    agentsNode.appendChild(card);
  });
}

function renderDetail(agent) {
  detailTitle.textContent = `${agent.name} (${agent.id})`;
  detailsNode.innerHTML = `
    <div><b>Action:</b> ${agent.current_action}</div>
    <div><b>Mood:</b> ${agent.mood}</div>
    <div><b>Goals:</b> ${agent.goals?.join(', ') || 'none'}</div>
    <div><b>Location:</b> (${agent.x}, ${agent.y})</div>
  `;

  memoriesNode.innerHTML = '';
  (agent.memories || []).slice().reverse().forEach((mem) => {
    const li = document.createElement('li');
    li.innerHTML = `<div>${mem.text}</div><div class="meta">${fmt(mem.timestamp)} · ${mem.source} · importance ${mem.importance}</div>`;
    memoriesNode.appendChild(li);
  });
}

async function loadAgents() {
  const res = await fetch('/api/agents');
  state.agents = await res.json();
  renderAgents();
  if (!state.selectedAgentId && state.agents.length) {
    state.selectedAgentId = state.agents[0].id;
    await loadAgent(state.selectedAgentId);
    renderAgents();
  }
}

async function loadAgent(agentId) {
  const res = await fetch(`/api/agents/${agentId}`);
  const agent = await res.json();
  renderDetail(agent);
}

askForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!state.selectedAgentId) return;
  const question = questionNode.value.trim();
  if (!question) return;

  const res = await fetch(`/api/agents/${state.selectedAgentId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  const data = await res.json();
  qaOutput.textContent = `Q: ${question}\nA: ${data.answer}`;
  questionNode.value = '';
  await loadAgent(state.selectedAgentId);
});

function connectEvents() {
  const ws = new WebSocket(`ws://${location.host}/ws/events`);

  ws.onopen = () => {
    statusNode.textContent = 'Live';
  };

  ws.onmessage = async (event) => {
    const payload = JSON.parse(event.data);

    if (payload.type === 'snapshot') {
      state.agents = payload.agents;
      renderAgents();
      if (!state.selectedAgentId && state.agents.length) {
        state.selectedAgentId = state.agents[0].id;
      }
      if (state.selectedAgentId) {
        await loadAgent(state.selectedAgentId);
      }
      return;
    }

    if (payload.type === 'tick') {
      state.agents = payload.agents;
      renderAgents();
      if (state.selectedAgentId) {
        await loadAgent(state.selectedAgentId);
      }
      statusNode.textContent = `Live · Tick ${payload.tick}`;
    }
  };

  ws.onclose = () => {
    statusNode.textContent = 'Disconnected. Reconnecting...';
    setTimeout(connectEvents, 1000);
  };
}

loadAgents().then(connectEvents);
