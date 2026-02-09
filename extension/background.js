// YouTube Video Downloader - Background Service Worker
// Intercepts video URLs and communicates with desktop app

const DESKTOP_APP_URL = 'http://localhost:9876';
let capturedVideos = {};

// Listen for video URL requests
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    const url = details.url;
    
    // Capture googlevideo.com URLs (actual video streams)
    if (url.includes('googlevideo.com') && url.includes('videoplayback')) {
      const videoId = extractVideoId(url);
      
      if (videoId && !capturedVideos[videoId]) {
        capturedVideos[videoId] = {
          url: url,
          timestamp: Date.now(),
          quality: extractQuality(url)
        };
        
        console.log('Captured video URL:', videoId);
      }
    }
  },
  { urls: ["*://*.googlevideo.com/*"] }
);

// Extract video ID from URL
function extractVideoId(url) {
  const match = url.match(/[?&]id=([^&]+)/);
  return match ? match[1] : null;
}

// Extract quality from URL parameters
function extractQuality(url) {
  const match = url.match(/[?&]quality=([^&]+)/);
  return match ? match[1] : 'unknown';
}

// Listen for messages from popup or content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getCapturedVideos') {
    sendResponse({ videos: capturedVideos });
  }
  
  if (request.action === 'sendToApp') {
    sendToDesktopApp(request.data)
      .then(response => sendResponse({ success: true, response }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }
  
  if (request.action === 'clearVideos') {
    capturedVideos = {};
    sendResponse({ success: true });
  }
});

// Send download request to desktop app
async function sendToDesktopApp(videoData) {
  try {
    const response = await fetch(`${DESKTOP_APP_URL}/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(videoData)
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to send to desktop app:', error);
    throw error;
  }
}

// Clean up old captured videos (older than 5 minutes)
setInterval(() => {
  const now = Date.now();
  const fiveMinutes = 5 * 60 * 1000;
  
  for (const [id, data] of Object.entries(capturedVideos)) {
    if (now - data.timestamp > fiveMinutes) {
      delete capturedVideos[id];
    }
  }
}, 60000); // Run every minute

console.log('YouTube Downloader extension loaded');
