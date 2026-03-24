const overviewGrid = document.getElementById('overview-grid');
const queuesTable = document.getElementById('queues-table');
const qualityNota = document.getElementById('quality-nota');
const qualityTaxa = document.getElementById('quality-taxa');
const qualityAlertas = document.getElementById('quality-alertas');
const integrationsList = document.getElementById('integrations-list');
const promptKeySelect = document.getElementById('prompt-key');
const promptContent = document.getElementById('prompt-content');
const promptNotes = document.getElementById('prompt-notes');
const promptVersions = document.getElementById('prompt-versions');
const publishVersion = document.getElementById('publish-version');
const rollbackVersion = document.getElementById('rollback-version');
const saveDraftBtn = document.getElementById('save-draft-btn');
const publishBtn = document.getElementById('publish-btn');
const rollbackBtn = document.getElementById('rollback-btn');
const logoutBtn = document.getElementById('logout-btn');

let promptsData = {};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  return response.json();
}

function metricCard(label, value) {
  const div = document.createElement('div');
  div.className = 'metric';
  div.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
  return div;
}

async function loadOverview() {
  const data = await requestJson('/api/dashboard/overview');
  overviewGrid.innerHTML = '';
  overviewGrid.appendChild(metricCard('Leads totais', data.leads_total));
  overviewGrid.appendChild(metricCard('Leads 24h', data.leads_24h));
  overviewGrid.appendChild(metricCard('Disparos 24h', data.disparos_24h));
  overviewGrid.appendChild(metricCard('Agendamentos 24h', data.agendamentos_24h));
  overviewGrid.appendChild(metricCard('Nota media 7d', data.nota_media_7d));
  overviewGrid.appendChild(metricCard('Alertas 7d', data.alertas_7d));
}

async function loadQueues() {
  const data = await requestJson('/api/dashboard/queues');
  queuesTable.innerHTML = '';
  data.queues.forEach((row) => {
    const tr = document.createElement('tr');
    const hasError = !!row.error;
    tr.innerHTML = `
      <td>${row.name}</td>
      <td>${row.messages}</td>
      <td>${row.messages_ready}</td>
      <td>${row.messages_unacknowledged}</td>
      <td>${row.consumers}</td>
      <td class="${hasError ? 'bad' : 'ok'}">${hasError ? 'erro' : row.state}</td>
    `;
    queuesTable.appendChild(tr);
  });
}

async function loadQuality() {
  const data = await requestJson('/api/dashboard/quality');
  qualityNota.innerHTML = '';
  qualityTaxa.innerHTML = '';
  qualityAlertas.innerHTML = '';

  Object.entries(data.nota_media_por_sdr || {}).forEach(([k, v]) => {
    const li = document.createElement('li');
    li.textContent = `${k}: ${v}`;
    qualityNota.appendChild(li);
  });

  Object.entries(data.taxa_aprovacao_primeira_tentativa_por_sdr || {}).forEach(([k, v]) => {
    const li = document.createElement('li');
    li.textContent = `${k}: ${v}%`;
    qualityTaxa.appendChild(li);
  });

  (data.alertas_recentes || []).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = `${item.sdr_origem} | nota ${item.nota} | tentativas ${item.tentativas}`;
    qualityAlertas.appendChild(li);
  });
}

async function loadIntegrations() {
  const data = await requestJson('/api/dashboard/integrations');
  integrationsList.innerHTML = '';
  (data.checks || []).forEach((check) => {
    const li = document.createElement('li');
    li.className = check.ok ? 'ok' : 'bad';
    li.textContent = `${check.name}: ${check.detail}`;
    integrationsList.appendChild(li);
  });
}

function renderPromptVersions() {
  const key = promptKeySelect.value;
  const versions = promptsData[key] || [];
  promptVersions.innerHTML = '';

  if (versions.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'Sem versoes';
    promptVersions.appendChild(li);
    promptContent.value = '';
    return;
  }

  versions.forEach((version) => {
    const li = document.createElement('li');
    li.textContent = `v${version.version} | ${version.status} | ${version.created_by}`;
    promptVersions.appendChild(li);
  });

  promptContent.value = versions[0].content;
}

async function loadPrompts() {
  const data = await requestJson('/api/prompts');
  promptsData = data.prompts || {};
  const keys = Object.keys(promptsData);

  const previous = promptKeySelect.value;
  promptKeySelect.innerHTML = '';
  keys.forEach((key) => {
    const option = document.createElement('option');
    option.value = key;
    option.textContent = key;
    promptKeySelect.appendChild(option);
  });

  if (previous && keys.includes(previous)) {
    promptKeySelect.value = previous;
  }

  renderPromptVersions();
}

saveDraftBtn?.addEventListener('click', async () => {
  const key = promptKeySelect.value;
  await requestJson('/api/prompts/draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt_key: key,
      content: promptContent.value,
      notes: promptNotes.value || null,
    }),
  });
  promptNotes.value = '';
  await loadPrompts();
});

publishBtn?.addEventListener('click', async () => {
  const key = promptKeySelect.value;
  const version = Number(publishVersion.value);
  if (!version) {
    return;
  }
  await requestJson('/api/prompts/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_key: key, version }),
  });
  publishVersion.value = '';
  await loadPrompts();
});

rollbackBtn?.addEventListener('click', async () => {
  const key = promptKeySelect.value;
  const version = Number(rollbackVersion.value);
  if (!version) {
    return;
  }
  await requestJson('/api/prompts/rollback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_key: key, version }),
  });
  rollbackVersion.value = '';
  await loadPrompts();
});

promptKeySelect?.addEventListener('change', renderPromptVersions);

logoutBtn?.addEventListener('click', async () => {
  await requestJson('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
});

async function initialLoad() {
  try {
    await Promise.all([loadOverview(), loadQueues(), loadQuality(), loadIntegrations(), loadPrompts()]);
  } catch (error) {
    console.error(error);
  }
}

initialLoad();
setInterval(() => {
  loadOverview().catch(console.error);
  loadQueues().catch(console.error);
  loadQuality().catch(console.error);
  loadIntegrations().catch(console.error);
}, 15000);
