/* Videorama Chrome Extension - Content Script
 * Detects media on the page and shares basic info with the popup.
 */

function findVideoUrl() {
  const videos = Array.from(document.querySelectorAll('video'));
  for (const video of videos) {
    if (video.currentSrc) return video.currentSrc;
    if (video.src) return video.src;
    const source = video.querySelector('source');
    if (source?.src) return source.src;
  }
  return null;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'VIDEORAMA_PAGE_INFO') {
    const videoUrl = findVideoUrl();
    sendResponse({
      pageUrl: window.location.href,
      pageTitle: document.title,
      videoUrl,
    });
  }
});
