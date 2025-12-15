const baseUrlInput = document.getElementById('baseUrl');
const libraryInput = document.getElementById('libraryId');
const formatSelect = document.getElementById('format');
const autoModeCheckbox = document.getElementById('autoMode');
const statusEl = document.getElementById('status');
const saveBtn = document.getElementById('saveBtn');

function setStatus(message) {
  statusEl.textContent = message;
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
  setStatus('Guardado');
  setTimeout(() => setStatus(''), 2000);
}

saveBtn.addEventListener('click', saveSettings);

loadSettings();
