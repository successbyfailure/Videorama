const baseUrlInput = document.getElementById('baseUrl');
const incognitoBaseUrlInput = document.getElementById('incognitoBaseUrl');
const libraryInput = document.getElementById('libraryId');
const formatSelect = document.getElementById('format');
const autoModeCheckbox = document.getElementById('autoMode');
const statusEl = document.getElementById('status');
const saveBtn = document.getElementById('saveBtn');
const libraryModeRadios = document.querySelectorAll('input[name="libraryMode"]');

function setStatus(message) {
  statusEl.textContent = message;
}

async function loadSettings() {
  const defaults = {
    baseUrl: '',
    incognitoBaseUrl: '',
    libraryId: '',
    format: 'video_max',
    autoMode: true,
    defaultLibraryMode: 'auto',
  };
  const stored = await chrome.storage.sync.get(defaults);
  baseUrlInput.value = stored.baseUrl || '';
  incognitoBaseUrlInput.value = stored.incognitoBaseUrl || '';
  libraryInput.value = stored.libraryId || '';
  formatSelect.value = stored.format || 'video_max';
  autoModeCheckbox.checked = stored.autoMode ?? true;
   (libraryModeRadios || []).forEach((radio) => {
    radio.checked = radio.value === (stored.defaultLibraryMode || 'auto');
  });
}

async function saveSettings() {
  await chrome.storage.sync.set({
    baseUrl: baseUrlInput.value.trim(),
    incognitoBaseUrl: incognitoBaseUrlInput.value.trim(),
    libraryId: libraryInput.value.trim(),
    format: formatSelect.value,
    autoMode: autoModeCheckbox.checked,
    defaultLibraryMode: Array.from(libraryModeRadios).find((r) => r.checked)?.value || 'auto',
  });
  setStatus('Guardado');
  setTimeout(() => setStatus(''), 2000);
}

saveBtn.addEventListener('click', saveSettings);

loadSettings();
