const params = new URLSearchParams(location.hash.slice(1));
const shareId = params.get('share');
const acceptToken = params.get('accept');
history.replaceState(null, '', location.pathname);

const start = document.querySelector('#start');
const stop = document.querySelector('#stop');
const consent = document.querySelector('#consent');
const precision = document.querySelector('#precision');
const status = document.querySelector('#status');
const last = document.querySelector('#last');
let uploadToken = null;
let timer = null;
let stopping = false;

function setStatus(message, kind = '') { status.textContent = message; status.dataset.kind = kind; }
function position() { return new Promise((resolve, reject) => navigator.geolocation?.getCurrentPosition(resolve, reject, {enableHighAccuracy: precision.value === 'exact', maximumAge: 0, timeout: 12000}) ?? reject(new Error('Geolocation is unavailable.'))); }

async function upload() {
  if (!uploadToken) return;
  const point = await position();
  const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}/locations`, {
    method: 'POST', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${uploadToken}`},
    body: JSON.stringify({latitude: point.coords.latitude, longitude: point.coords.longitude, accuracy_m: point.coords.accuracy, observed_at: new Date(point.timestamp).toISOString()}),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'Upload failed.');
  last.textContent = `Last sent ${new Date(body.observed_at).toLocaleTimeString()} · ${body.precision} · accuracy ${Math.round(body.accuracy_m || 0)} m`;
  setStatus('Sharing is active. This page must remain visible.', 'success');
}

async function stopShare() {
  if (!uploadToken || stopping) return;
  stopping = true;
  clearInterval(timer); timer = null;
  try { await fetch(`/api/shares/${encodeURIComponent(shareId)}/stop`, {method: 'POST', headers: {Authorization: `Bearer ${uploadToken}`}, keepalive: true}); }
  finally { uploadToken = null; start.disabled = true; stop.disabled = true; setStatus('Stopped. The stored point and upload capability were erased.', 'success'); stopping = false; }
}

start.addEventListener('click', async () => {
  if (!shareId || !acceptToken) return setStatus('This sharing link is incomplete.', 'error');
  if (!consent.checked) return setStatus('Explicit consent is required.', 'error');
  start.disabled = true;
  try {
    const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}/accept`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({accept_token: acceptToken, precision: precision.value})});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || 'Invitation could not be accepted.');
    uploadToken = body.upload_token;
    stop.disabled = false;
    consent.disabled = true; precision.disabled = true;
    await upload();
    timer = setInterval(() => upload().catch((error) => setStatus(error.message, 'error')), body.upload_interval_seconds * 1000);
  } catch (error) { start.disabled = false; setStatus(error.message, 'error'); }
});
stop.addEventListener('click', stopShare);
document.addEventListener('visibilitychange', () => { if (document.hidden) stopShare(); });
window.addEventListener('pagehide', stopShare);
if (!shareId || !acceptToken) { start.disabled = true; setStatus('This sharing link is incomplete.', 'error'); }
