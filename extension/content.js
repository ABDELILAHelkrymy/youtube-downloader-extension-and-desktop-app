// YouTube Video Downloader - Content Script
// Extracts video metadata from YouTube pages

function getVideoMetadata() {
  const videoId = new URLSearchParams(window.location.search).get('v');
  
  if (!videoId) return null;
  
  // Try to get title from different possible elements
  const titleElement = document.querySelector('h1.ytd-video-primary-info-renderer') ||
                       document.querySelector('h1.title') ||
                       document.querySelector('meta[name="title"]');
  
  const title = titleElement ? 
    (titleElement.textContent || titleElement.getAttribute('content')).trim() : 
    'Unknown Title';
  
  // Get channel name
  const channelElement = document.querySelector('ytd-channel-name a') ||
                        document.querySelector('#owner-name a');
  const channel = channelElement ? channelElement.textContent.trim() : 'Unknown Channel';
  
  // Get duration from video player
  let duration = 'Unknown';
  const videoElement = document.querySelector('video');
  if (videoElement && videoElement.duration) {
    const mins = Math.floor(videoElement.duration / 60);
    const secs = Math.floor(videoElement.duration % 60);
    duration = `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  return {
    videoId,
    title,
    channel,
    duration,
    url: window.location.href
  };
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getMetadata') {
    const metadata = getVideoMetadata();
    sendResponse({ metadata });
  }
});

console.log('YouTube Downloader content script loaded');
