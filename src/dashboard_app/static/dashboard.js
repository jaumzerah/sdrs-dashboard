const elements = {
  overviewGrid: document.getElementById('overview-grid'),
  queuesTable: document.getElementById('queues-table'),
  queuesMobileCards: document.getElementById('queues-mobile-cards'),
  qualityNota: document.getElementById('quality-nota'),
  qualityTaxa: document.getElementById('quality-taxa'),
  qualityAlertas: document.getElementById('quality-alertas'),
  integrationsList: document.getElementById('integrations-list'),
  promptKeySelect: document.getElementById('prompt-key'),
  promptContent: document.getElementById('prompt-content'),
  promptNotes: document.getElementById('prompt-notes'),
  promptVersions: document.getElementById('prompt-versions'),
  publishVersion: document.getElementById('publish-version'),
  rollbackVersion: document.getElementById('rollback-version'),
  saveDraftBtn: document.getElementById('save-draft-btn'),
  publishBtn: document.getElementById('publish-btn'),
  rollbackBtn: document.getElementById('rollback-btn'),
  logoutBtn: document.getElementById('logout-btn'),
  globalHealth: document.getElementById('global-health'),
  refreshMeta: document.getElementById('refresh-meta'),
  activeViewMeta: document.getElementById('active-view-meta'),
  tabOps: document.getElementById('tab-ops'),
  tabPrompts: document.getElementById('tab-prompts'),
  opsView: document.getElementById('ops-view'),
  promptsView: document.getElementById('prompts-view'),
  toast: document.getElementById('toast'),
  overviewState: document.getElementById('overview-state'),
  queuesState: document.getElementById('queues-state'),
  qualityState: document.getElementById('quality-state'),
  integrationsState: document.getElementById('integrations-state'),
  promptsState: document.getElementById('prompts-state'),
};

const appState = {
  promptsData: {},
  lastSuccessAt: null,
  failures: {},
  activeView: 'ops',
};

function showToast(message, kind = 'ok') {
  if (!elements.toast) return;
  elements.toast.textContent = message;
  elements.toast.className = `toast visible ${kind}`;
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => {
    elements.toast.className = 'toast';
  }, 3000);
}

function safeSetState(node, text) {
  if (node) node.textContent = text;
}

function setModuleState(moduleName, ok, detail) {
  const map = {
    overview: elements.overviewState,
    queues: elements.queuesState,
    quality: elements.qualityState,
    integrations: elements.integrationsState,
    prompts: elements.promptsState,
  };
  const node = map[moduleName];
  if (!node) return;
  node.textContent = detail;
  node.className = `panel-state ${ok ? 'ok' : 'bad'}`;
}

function updateGlobalHealth() {
  const failedModules = Object.keys(appState.failures).filter((key) => appState.failures[key]);
  if (!elements.globalHealth) return;

  if (failedModules.length === 0 && appState.lastSuccessAt) {
    elements.globalHealth.className = 'status-badge status-ok';
    elements.globalHealth.textContent = 'Painel operacional sincronizado';
  } else if (failedModules.length > 0) {
    elements.globalHealth.className = 'status-badge status-bad';
    elements.globalHealth.textContent = `Atencao: falha em ${failedModules.join(', ')}`;
  } else {
    elements.globalHealth.className = 'status-badge status-loading';
    elements.globalHealth.textContent = 'Sincronizando dados...';
  }

  if (elements.refreshMeta) {
    if (appState.lastSuccessAt) {
      const clock = appState.lastSuccessAt.toLocaleTimeString('pt-BR');
      elements.refreshMeta.textContent = `Ultima atualizacao: ${clock}`;
    } else {
      elements.refreshMeta.textContent = 'Aguardando primeira leitura';
    }
  }
}

function markModule(moduleName, ok) {
  appState.failures[moduleName] = !ok;
  if (ok) appState.lastSuccessAt = new Date();
  updateGlobalHealth();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  return response.json();
}

function createMetricCard(label, value) {
  const div = document.createElement('div');
  div.className = 'metric';

  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;

  const v = document.createElement('div');
  v.className = 'value';
  v.textContent = String(value);

  div.appendChild(l);
  div.appendChild(v);
  return div;
}

function buildStatusPill(ok, text) {
  const span = document.createElement('span');
  span.className = `status-pill ${ok ? 'ok' : 'bad'}`;
  span.textContent = text;
  return span;
}

function clearNode(node) {
  while (node && node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

async function loadOverview() {
  const data = await requestJson('/api/dashboard/overview');
  clearNode(elements.overviewGrid);
  elements.overviewGrid.appendChild(createMetricCard('Leads totais', data.leads_total));
  elements.overviewGrid.appendChild(createMetricCard('Leads 24h', data.leads_24h));
  elements.overviewGrid.appendChild(createMetricCard('Disparos 24h', data.disparos_24h));
  elements.overviewGrid.appendChild(createMetricCard('Agendamentos 24h', data.agendamentos_24h));
  elements.overviewGrid.appendChild(createMetricCard('Nota media 7d', data.nota_media_7d));
  elements.overviewGrid.appendChild(createMetricCard('Alertas 7d', data.alertas_7d));
}

function renderQueueMobileCards(rows) {
  clearNode(elements.queuesMobileCards);
  rows.forEach((row) => {
    const card = document.createElement('article');
    card.className = 'queue-card';

    const title = document.createElement('h4');
    title.textContent = row.name;
    card.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'queue-grid';
    [
      `Msgs: ${row.messages}`,
      `Ready: ${row.messages_ready}`,
      `Unacked: ${row.messages_unacknowledged}`,
      `Consumers: ${row.consumers}`,
    ].forEach((txt) => {
      const item = document.createElement('span');
      item.textContent = txt;
      grid.appendChild(item);
    });

    card.appendChild(grid);
    card.appendChild(buildStatusPill(!row.error, row.error ? 'erro' : row.state));
    elements.queuesMobileCards.appendChild(card);
  });
}

async function loadQueues() {
  const data = await requestJson('/api/dashboard/queues');
  const rows = data.queues || [];
  clearNode(elements.queuesTable);

  rows.forEach((row) => {
    const tr = document.createElement('tr');
    const hasError = Boolean(row.error);
    const columns = [
      row.name,
      row.messages,
      row.messages_ready,
      row.messages_unacknowledged,
      row.consumers,
    ];

    columns.forEach((col) => {
      const td = document.createElement('td');
      td.textContent = String(col);
      tr.appendChild(td);
    });

    const statusTd = document.createElement('td');
    statusTd.appendChild(buildStatusPill(!hasError, hasError ? 'erro' : row.state));
    tr.appendChild(statusTd);
    elements.queuesTable.appendChild(tr);
  });

  renderQueueMobileCards(rows);
}

function renderListFromObject(target, obj, suffix = '') {
  clearNode(target);
  const entries = Object.entries(obj || {});
  if (entries.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'Sem dados no periodo.';
    target.appendChild(li);
    return;
  }
  entries.forEach(([k, v]) => {
    const li = document.createElement('li');
    li.textContent = `${k}: ${v}${suffix}`;
    target.appendChild(li);
  });
}

async function loadQuality() {
  const data = await requestJson('/api/dashboard/quality');
  renderListFromObject(elements.qualityNota, data.nota_media_por_sdr || {});
  renderListFromObject(elements.qualityTaxa, data.taxa_aprovacao_primeira_tentativa_por_sdr || {}, '%');

  clearNode(elements.qualityAlertas);
  const alerts = data.alertas_recentes || [];
  if (alerts.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'Nenhum alerta recente.';
    elements.qualityAlertas.appendChild(li);
    return;
  }
  alerts.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = `${item.sdr_origem} | nota ${item.nota} | tentativas ${item.tentativas}`;
    elements.qualityAlertas.appendChild(li);
  });
}

async function loadIntegrations() {
  const data = await requestJson('/api/dashboard/integrations');
  clearNode(elements.integrationsList);
  (data.checks || []).forEach((check) => {
    const li = document.createElement('li');
    li.className = check.ok ? 'ok' : 'bad';
    li.textContent = `${check.name}: ${check.detail}`;
    elements.integrationsList.appendChild(li);
  });
}

function renderPromptVersions() {
  const key = elements.promptKeySelect.value;
  const versions = appState.promptsData[key] || [];
  clearNode(elements.promptVersions);

  if (versions.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'Sem versoes registradas';
    elements.promptVersions.appendChild(li);
    elements.promptContent.value = '';
    return;
  }

  versions.forEach((version) => {
    const li = document.createElement('li');
    li.textContent = `v${version.version} | ${version.status} | ${version.created_by}`;
    elements.promptVersions.appendChild(li);
  });

  elements.promptContent.value = versions[0].content || '';
}

async function loadPrompts() {
  const data = await requestJson('/api/prompts');
  appState.promptsData = data.prompts || {};
  const keys = Object.keys(appState.promptsData);

  const previous = elements.promptKeySelect.value;
  clearNode(elements.promptKeySelect);
  keys.forEach((key) => {
    const option = document.createElement('option');
    option.value = key;
    option.textContent = key;
    elements.promptKeySelect.appendChild(option);
  });

  if (previous && keys.includes(previous)) {
    elements.promptKeySelect.value = previous;
  }

  renderPromptVersions();
}

function activateView(view) {
  appState.activeView = view;
  const ops = view === 'ops';
  elements.opsView.classList.toggle('hidden', !ops);
  elements.promptsView.classList.toggle('hidden', ops);
  elements.tabOps.classList.toggle('active', ops);
  elements.tabPrompts.classList.toggle('active', !ops);
  elements.tabOps.setAttribute('aria-selected', String(ops));
  elements.tabPrompts.setAttribute('aria-selected', String(!ops));
  safeSetState(elements.activeViewMeta, `Visao: ${ops ? 'Operacao' : 'Prompt Studio'}`);
}

async function loadModule(moduleName, fn) {
  try {
    await fn();
    markModule(moduleName, true);
    setModuleState(moduleName, true, 'Atualizado');
  } catch (error) {
    markModule(moduleName, false);
    setModuleState(moduleName, false, 'Falha na atualizacao');
    showToast(`Falha em ${moduleName}: ${String(error).slice(0, 120)}`, 'bad');
  }
}

elements.saveDraftBtn?.addEventListener('click', async () => {
  const key = elements.promptKeySelect.value;
  if (!key) return;
  await requestJson('/api/prompts/draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt_key: key,
      content: elements.promptContent.value,
      notes: elements.promptNotes.value || null,
    }),
  });
  elements.promptNotes.value = '';
  await loadModule('prompts', loadPrompts);
  showToast('Draft salvo com sucesso.');
});

elements.publishBtn?.addEventListener('click', async () => {
  const key = elements.promptKeySelect.value;
  const version = Number(elements.publishVersion.value);
  if (!version) return;
  if (!window.confirm(`Publicar v${version} de ${key}?`)) return;
  await requestJson('/api/prompts/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_key: key, version }),
  });
  elements.publishVersion.value = '';
  await loadModule('prompts', loadPrompts);
  showToast(`v${version} publicada em ${key}.`);
});

elements.rollbackBtn?.addEventListener('click', async () => {
  const key = elements.promptKeySelect.value;
  const version = Number(elements.rollbackVersion.value);
  if (!version) return;
  if (!window.confirm(`Executar rollback de ${key} para v${version}?`)) return;
  await requestJson('/api/prompts/rollback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_key: key, version }),
  });
  elements.rollbackVersion.value = '';
  await loadModule('prompts', loadPrompts);
  showToast(`Rollback executado para v${version}.`);
});

elements.promptKeySelect?.addEventListener('change', renderPromptVersions);

elements.logoutBtn?.addEventListener('click', async () => {
  if (!window.confirm('Encerrar sessao do painel?')) return;
  await requestJson('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
});

elements.tabOps?.addEventListener('click', () => activateView('ops'));
elements.tabPrompts?.addEventListener('click', () => activateView('prompts'));

async function refreshOpsModules() {
  await Promise.all([
    loadModule('overview', loadOverview),
    loadModule('queues', loadQueues),
    loadModule('quality', loadQuality),
    loadModule('integrations', loadIntegrations),
  ]);
}

async function initialLoad() {
  activateView('ops');
  await refreshOpsModules();
  await loadModule('prompts', loadPrompts);
}

initialLoad().catch((error) => {
  showToast(`Falha na inicializacao: ${String(error).slice(0, 120)}`, 'bad');
});

setInterval(() => {
  refreshOpsModules();
}, 15000);
