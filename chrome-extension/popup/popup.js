const baseUrlInput = document.getElementById('baseUrl');
const importUrlInput = document.getElementById('importUrl');
const libraryInput = document.getElementById('libraryId');
const formatSelect = document.getElementById('format');
const autoModeCheckbox = document.getElementById('autoMode');
const statusEl = document.getElementById('status');
const importBtn = document.getElementById('importBtn');
const openOptionsBtn = document.getElementById('openOptions');

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
  const stored = await chrome.storage.sync.get(defaults);
  baseUrlInput.value = stored.baseUrl || '';
  libraryInput.value = stored.libraryId || '';
  formatSelect.value = stored.format || 'video_max';
  autoModeCheckbox.checked = stored.autoMode ?? true;
}

async function saveSettings() {
  await chrome.storage.sync.set({
    baseUrl: baseUrlInput.value.trim(),
    libraryId: libraryInput.value.trim(),
    format: formatSelect.value,
    autoMode: autoModeCheckbox.checked,
  });
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

async function handleImport() {
  setStatus('Enviando import...', 'info');
  importBtn.disabled = true;

  const baseUrl = normalizeBaseUrl(baseUrlInput.value.trim());
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
    library_id: libraryInput.value.trim() || null,
    format: formatSelect.value,
    auto_mode: autoModeCheckbox.checked,
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
    setStatus(
      data.entry_uuid
        ? 'Import completado y agregado a la librería.'
        : data.inbox_id
        ? 'Enviado al inbox para revisión.'
        : 'Import iniciado, revisa los jobs en Videorama.',
      'success'
    );

    await saveSettings();
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
  await detectPageInfo();
})();
