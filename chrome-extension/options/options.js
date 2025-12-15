const baseUrlInput = document.getElementById('baseUrl');
const libraryInput = document.getElementById('libraryId');
const incognitoLibraryInput = document.getElementById('incognitoLibraryId');
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
    libraryId: '',
    incognitoLibraryId: '',
    format: 'video_max',
    autoMode: true,
    defaultLibraryMode: 'auto',
  };
  const stored = await chrome.storage.sync.get(defaults);
  baseUrlInput.value = stored.baseUrl || '';
  libraryInput.value = stored.libraryId || '';
  incognitoLibraryInput.value = stored.incognitoLibraryId || '';
  formatSelect.value = stored.format || 'video_max';
  autoModeCheckbox.checked = stored.autoMode ?? true;
   (libraryModeRadios || []).forEach((radio) => {
    radio.checked = radio.value === (stored.defaultLibraryMode || 'auto');
  });
}

async function saveSettings() {
  await chrome.storage.sync.set({
    baseUrl: baseUrlInput.value.trim(),
    libraryId: libraryInput.value.trim(),
    incognitoLibraryId: incognitoLibraryInput.value.trim(),
    format: formatSelect.value,
    autoMode: autoModeCheckbox.checked,
    defaultLibraryMode: Array.from(libraryModeRadios).find((r) => r.checked)?.value || 'auto',
  });
  setStatus('Guardado');
  setTimeout(() => setStatus(''), 2000);
}

saveBtn.addEventListener('click', saveSettings);

loadSettings();
