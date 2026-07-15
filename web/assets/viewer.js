const params = new URLSearchParams(location.hash.slice(1));
const shareId = params.get('share');
const viewerToken = params.get('view');
history.replaceState(null, '', location.pathname);

const status = document.querySelector('#status');
const panel = document.querySelector('#location');
const mapLink = document.querySelector('#mapLink');
let timer = null;
function setStatus(message, kind = '') { status.textContent = message; status.dataset.kind = kind; }

async function load() {
  if (!shareId || !viewerToken) return setStatus('This viewer link is incomplete.', 'error');
  try {
    const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}/location`, {headers: {Authorization: `Bearer ${viewerToken}`}});
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || 'Location could not be loaded.');
    if (!body.location) { panel.hidden = true; return setStatus(body.status === 'awaiting_acceptance' ? 'Waiting for the recipient to accept.' : `Share is ${body.status}.`, body.status === 'sharing' ? '' : 'error'); }
    const point = body.location;
    document.querySelector('#label').textContent = body.label;
    document.querySelector('#coordinates').textContent = `${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}`;
    const age = Math.max(0, Math.round((Date.now() - new Date(point.observed_at).getTime()) / 1000));
    document.querySelector('#meta').textContent = `${point.precision} · accuracy ${Math.round(point.accuracy_m || 0)} m · observed ${age}s ago · expires ${new Date(body.expires_at).toLocaleTimeString()}`;
    mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(point.latitude)}&mlon=${encodeURIComponent(point.longitude)}#map=17/${encodeURIComponent(point.latitude)}/${encodeURIComponent(point.longitude)}`;
    panel.hidden = false; setStatus('Authorized latest point loaded.', 'success');
  } catch (error) { panel.hidden = true; setStatus(error.message, 'error'); }
}

async function revoke() {
  if (!shareId || !viewerToken) return;
  const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}/stop`, {method: 'POST', headers: {Authorization: `Bearer ${viewerToken}`}});
  if (response.ok) { clearInterval(timer); panel.hidden = true; setStatus('Stopped. The stored point and upload capability were erased.', 'success'); }
  else { const body = await response.json(); setStatus(body.detail || 'Could not stop share.', 'error'); }
}

document.querySelector('#refresh').addEventListener('click', load);
document.querySelector('#revoke').addEventListener('click', revoke);
document.addEventListener('visibilitychange', () => { clearInterval(timer); if (!document.hidden) { load(); timer = setInterval(load, 15000); } });
load(); timer = setInterval(load, 15000);
