// YouTube Video Downloader - Popup Script

const DESKTOP_APP_URL = 'http://localhost:9876';

const elements = {
  status: document.getElementById('status'),
  videoInfo: document.getElementById('videoInfo'),
  videoTitle: document.getElementById('videoTitle'),
  videoChannel: document.getElementById('videoChannel'),
  videoDuration: document.getElementById('videoDuration'),
  formatSelect: document.getElementById('formatSelect'),
  downloadBtn: document.getElementById('downloadBtn')
};

let currentVideoData = null;

// Check if desktop app is running
async function checkDesktopApp() {
  try {
    const response = await fetch(`${DESKTOP_APP_URL}/ping`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    
    if (response.ok) {
      showStatus('✓ Desktop app connected', 'success');
      return true;
    }
  } catch (error) {
    showStatus('✗ Desktop app not running. Please start ytdownload_ui.pyw', 'error');
  }
  return false;
}

// Get current tab's video metadata
async function getCurrentVideo() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (!tab.url || !tab.url.includes('youtube.com/watch')) {
    showStatus('Not on a YouTube video page', 'error');
    return null;
  }
  
  // Get metadata from content script
  const response = await chrome.tabs.sendMessage(tab.id, { action: 'getMetadata' });
  
  if (response && response.metadata) {
    return response.metadata;
  }
  
  return null;
}

// Show status message
function showStatus(message, type = 'info') {
  elements.status.textContent = message;
  elements.status.className = type === 'error' ? 'error' : 
                               type === 'success' ? 'success' : 'status';
}

// Display video information
function displayVideoInfo(metadata) {
  if (!metadata) return;
  
  elements.videoTitle.textContent = metadata.title;
  elements.videoChannel.textContent = `Channel: ${metadata.channel}`;
  elements.videoDuration.textContent = `Duration: ${metadata.duration}`;
  elements.videoInfo.style.display = 'block';
  
  currentVideoData = metadata;
  elements.downloadBtn.disabled = false;
}

// Send download request to desktop app
async function downloadVideo() {
  if (!currentVideoData) return;
  
  elements.downloadBtn.disabled = true;
  showStatus('Sending to desktop app...', 'info');
  
  const format = elements.formatSelect.value;
  
  const downloadData = {
    url: currentVideoData.url,
    title: currentVideoData.title,
    channel: currentVideoData.channel,
    format: format
  };
  
  try {
    const response = await chrome.runtime.sendMessage({
      action: 'sendToApp',
      data: downloadData
    });
    
    if (response.success) {
      showStatus('✓ Download started in desktop app!', 'success');
      setTimeout(() => window.close(), 2000);
    } else {
      showStatus(`✗ Error: ${response.error}`, 'error');
      elements.downloadBtn.disabled = false;
    }
  } catch (error) {
    showStatus(`✗ Failed to communicate: ${error.message}`, 'error');
    elements.downloadBtn.disabled = false;
  }
}

// Initialize popup
async function init() {
  // Check desktop app
  const appRunning = await checkDesktopApp();
  
  // Get current video metadata
  const metadata = await getCurrentVideo();
  
  if (metadata) {
    displayVideoInfo(metadata);
  } else if (appRunning) {
    showStatus('Navigate to a YouTube video to download', 'info');
  }
}

// Event listeners
elements.downloadBtn.addEventListener('click', downloadVideo);

// Initialize when popup opens
init();
