const importUrlInput = document.getElementById('importUrl');
const statusEl = document.getElementById('status');
const importBtn = document.getElementById('importBtn');
const openOptionsBtn = document.getElementById('openOptions');
const recentList = document.getElementById('recentList');
const librarySelect = document.getElementById('librarySelect');
const progressCard = document.getElementById('progress');
const progressValue = document.getElementById('progressValue');
const progressBarInner = document.getElementById('progressBarInner');
const progressMessage = document.getElementById('progressMessage');

let settings = {
  baseUrl: '',
  incognitoLibraryId: '',
  libraryId: '',
  format: 'video_max',
  autoMode: true,
  defaultLibraryMode: 'auto',
};

let recentImports = [];
let pollInterval = null;

function setStatus(message, type = 'info') {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

async function loadSettings() {
  const defaults = {
    baseUrl: '',
    incognitoLibraryId: '',
    libraryId: '',
    format: 'video_max',
    autoMode: true,
    defaultLibraryMode: 'auto',
  };
  settings = await chrome.storage.sync.get(defaults);
  hydrateLibrarySelect();
}

async function detectPageInfo() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const tabUrl = tab?.url || '';

    let detected = { pageUrl: tabUrl, videoUrl: null, pageTitle: tab?.title || '' };

    if (tab?.id) {
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { type: 'VIDEORAMA_PAGE_INFO' });
        detected = { ...detected, ...response };
      } catch (err) {
        // Content script may not be injected (e.g., chrome://). Fallback silently.
      }
    }

    importUrlInput.value = detected.videoUrl || detected.pageUrl || '';
  } catch (error) {
    setStatus(`No se pudo detectar la URL: ${error.message}`, 'error');
  }
}

function normalizeBaseUrl(url) {
  return url.replace(/\/$/, '');
}

function hydrateLibrarySelect() {
  if (!librarySelect) return;
  librarySelect.innerHTML = '';
  const defaultMode = settings.defaultLibraryMode || 'auto';
  const isIncognito = chrome.extension?.inIncognitoContext;
  const preferredLibrary = isIncognito
    ? (settings.incognitoLibraryId || '').trim()
    : (settings.libraryId || '').trim();

  // Always include Auto
  librarySelect.appendChild(new Option('Auto (LLM)', ''));

  // Fetch libraries from Videorama
  const baseUrl = normalizeBaseUrl(settings.baseUrl || '');
  if (!baseUrl) {
    // fallback to configured IDs if baseUrl missing
    if (preferredLibrary) {
      librarySelect.appendChild(new Option(`Librería: ${preferredLibrary}`, preferredLibrary));
    }
    librarySelect.value = defaultMode === 'auto' ? '' : preferredLibrary;
    return;
  }

  fetch(`${baseUrl}/api/v1/libraries`)
    .then((res) => res.ok ? res.json() : [])
    .then((libs) => {
      libs.forEach((lib) => {
        librarySelect.appendChild(new Option(`${lib.icon || ''} ${lib.name}`, lib.id));
      });
      librarySelect.value = defaultMode === 'auto' ? '' : preferredLibrary || '';
    })
    .catch(() => {
      if (preferredLibrary) {
        librarySelect.appendChild(new Option(`Librería: ${preferredLibrary}`, preferredLibrary));
      }
      librarySelect.value = defaultMode === 'auto' ? '' : preferredLibrary;
    });
}

async function loadRecentImports() {
  try {
    const stored = await chrome.storage.session.get({ recentImports: [] });
    recentImports = stored.recentImports || [];
    renderRecentImports();
  } catch (err) {
    recentImports = [];
  }
}

async function saveRecentImports() {
  recentImports = recentImports.slice(0, 5);
  await chrome.storage.session.set({ recentImports });
}

function renderRecentImports() {
  if (!recentList) return;
  recentList.innerHTML = '';

  if (!recentImports.length) {
    const li = document.createElement('li');
    li.className = 'recent-item';
    li.textContent = 'Sin importaciones en esta sesión.';
    recentList.appendChild(li);
    return;
  }

  for (const item of recentImports) {
    const li = document.createElement('li');
    li.className = 'recent-item';

    const urlEl = document.createElement('div');
    urlEl.className = 'recent-url';
    urlEl.textContent = item.url;

    const meta = document.createElement('div');
    meta.className = 'recent-meta';
    const statusText = item.status || 'pendiente';
    meta.innerHTML = `<span class="badge">${statusText}</span><span>${new Date(item.timestamp).toLocaleTimeString()}</span>`;

    li.appendChild(meta);
    li.appendChild(urlEl);
    recentList.appendChild(li);
  }
}

function startPolling(jobId, baseUrl) {
  stopPolling();
  if (!jobId) return;
  progressCard.hidden = false;
  progressValue.textContent = '0%';
  progressBarInner.style.width = '0%';
  progressMessage.textContent = '';

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`${baseUrl}/api/v1/jobs/${jobId}`);
      if (!res.ok) throw new Error('Error obteniendo el job');
      const job = await res.json();
      const pct = Math.round((job.progress || 0) * 100);
      progressValue.textContent = `${pct}%`;
      progressBarInner.style.width = `${pct}%`;
      progressMessage.textContent = job.message || job.status || '';

      if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
        stopPolling();
        progressMessage.textContent = job.status === 'completed' ? 'Completado' : (job.error || job.status);
        updateRecentStatus(jobId, job.status === 'completed' ? 'importado' : 'error');
      }
    } catch (err) {
      stopPolling();
      progressMessage.textContent = `Error al consultar el job`;
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function updateRecentStatus(jobId, status) {
  recentImports = recentImports.map((item) =>
    item.job_id === jobId ? { ...item, status } : item
  );
  await saveRecentImports();
  renderRecentImports();
}

async function handleImport() {
  setStatus('Enviando import...', 'info');
  importBtn.disabled = true;

  const baseUrl = normalizeBaseUrl(settings.baseUrl || '');
  const url = importUrlInput.value.trim();

  if (!baseUrl) {
    setStatus('Configura la API base URL en Opciones.', 'error');
    importBtn.disabled = false;
    return;
  }

  if (!url) {
    setStatus('Introduce una URL para importar.', 'error');
    importBtn.disabled = false;
    return;
  }

  const payload = {
    url,
    library_id: (librarySelect.value || '').trim() || null,
    format: settings.format || 'video_max',
    auto_mode: settings.autoMode ?? true,
    imported_by: 'chrome-extension',
  };

  try {
    const endpoint = `${baseUrl}/api/v1/import/url`;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }

    const data = await res.json();
    // Log to session history (keep last 5)
    recentImports.unshift({
      url,
      status: data.entry_uuid
        ? 'importado'
        : data.inbox_id
        ? 'inbox'
        : 'en progreso',
      job_id: data.job_id,
      timestamp: Date.now(),
    });
    await saveRecentImports();
    renderRecentImports();

    if (data.job_id) {
      startPolling(data.job_id, baseUrl);
    }

    setStatus(
      data.entry_uuid
        ? 'Import completado y agregado a la librería.'
        : data.inbox_id
        ? 'Enviado al inbox para revisión.'
        : 'Import iniciado, revisa los jobs en Videorama.',
      'success'
    );
  } catch (error) {
    setStatus(`Error al importar: ${error.message}`, 'error');
  } finally {
    importBtn.disabled = false;
  }
}

openOptionsBtn.addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

importBtn.addEventListener('click', handleImport);

(async function init() {
  await loadSettings();
  await loadRecentImports();
  await detectPageInfo();
})();
