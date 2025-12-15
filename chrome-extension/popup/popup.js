const importUrlInput = document.getElementById('importUrl');
const statusEl = document.getElementById('status');
const importBtn = document.getElementById('importBtn');
const openOptionsBtn = document.getElementById('openOptions');
const recentList = document.getElementById('recentList');

let settings = {
  baseUrl: '',
  libraryId: '',
  format: 'video_max',
  autoMode: true,
};

let recentImports = [];

function setStatus(message, type = 'info') {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

async function loadSettings() {
  const defaults = {
    baseUrl: '',
    libraryId: '',
    format: 'video_max',
    autoMode: true,
  };
  settings = await chrome.storage.sync.get(defaults);
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
    library_id: (settings.libraryId || '').trim() || null,
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
