const form = document.querySelector('#createForm');
const status = document.querySelector('#status');
const result = document.querySelector('#result');

function setStatus(message, kind = '') { status.textContent = message; status.dataset.kind = kind; }

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  setStatus('Creating short-lived capabilities…');
  result.hidden = true;
  try {
    const response = await fetch('/api/shares', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({label: form.label.value.trim(), duration_minutes: Number(form.duration.value)}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || 'Could not create share.');
    document.querySelector('#shareUrl').value = body.share_url;
    document.querySelector('#viewerUrl').value = body.viewer_url;
    document.querySelector('#expiry').textContent = `Expires ${new Date(body.expires_at).toLocaleString()}. Only the latest point is retained.`;
    result.hidden = false;
    setStatus('Links created. Send only the sharing link to the person who will choose whether to share.', 'success');
  } catch (error) { setStatus(error.message, 'error'); }
});

document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-copy]');
  if (!target) return;
  const field = document.querySelector(`#${target.dataset.copy}`);
  try { await navigator.clipboard.writeText(field.value); target.textContent = 'Copied'; }
  catch { field.select(); setStatus('Clipboard permission was unavailable; copy the selected link manually.', 'error'); }
});
