/* Videorama Chrome Extension - Background Service Worker (MV3)
 * - Seeds default settings on install
 */

const DEFAULT_SETTINGS = {
  baseUrl: 'http://localhost',
  libraryId: '',
  format: 'video_max',
  autoMode: true,
  defaultLibraryMode: 'auto',
};

chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.sync.get();
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
});
