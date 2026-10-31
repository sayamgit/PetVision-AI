const locationButton = document.getElementById('share-location');
if (locationButton) {
  const lat = document.getElementById('id_latitude');
  const lon = document.getElementById('id_longitude');
  const consent = document.getElementById('id_share_location');
  const status = document.getElementById('location-status');
  const form = document.getElementById('sighting-form');
  let requestId = 0, pending = false;
  const clearCoordinates = () => { lat.value = ''; lon.value = ''; consent.checked = false; };
  const finish = () => { pending = false; locationButton.disabled = false; form.setAttribute('aria-busy', 'false'); };
  if (lat.value && lon.value) status.textContent = `Selected coordinates: ${lat.value}, ${lon.value}`;
  locationButton.addEventListener('click', () => {
    const currentRequest = ++requestId;
    // A failed retry must never leave previously agreed coordinates selected.
    clearCoordinates();
    if (!window.isSecureContext) {
      status.textContent = 'Location sharing needs a secure HTTPS page. You can type a landmark instead.';
      finish(); return;
    }
    if (!navigator.geolocation) {
      status.textContent = 'Location is unavailable in this browser. Please type a landmark instead.';
      finish(); return;
    }
    pending = true; locationButton.disabled = true; form.setAttribute('aria-busy', 'true');
    status.textContent = 'Waiting for your browser location permission…';
    const failed = error => {
      if (currentRequest !== requestId) return;
      const reason = ({1: 'Location permission was denied.', 2: 'Your device could not determine its location.', 3: 'The location request timed out.'})[error?.code] || 'Location could not be obtained.';
      clearCoordinates(); finish();
      status.textContent = `${reason} No coordinates are selected. You can retry or type a landmark instead.`;
    };
    try {
      navigator.geolocation.getCurrentPosition(position => {
        if (currentRequest !== requestId) return;
        lat.value = position.coords.latitude.toFixed(6);
        lon.value = position.coords.longitude.toFixed(6);
        consent.checked = false; finish();
        status.textContent = `Selected coordinates: ${lat.value}, ${lon.value}. Check the consent box, then send your report to share them with the owner.`;
      }, failed, {enableHighAccuracy: true, timeout: 10000, maximumAge: 0});
    } catch (error) { failed(error); }
  });
  document.getElementById('clear-location').addEventListener('click', () => {
    requestId++; clearCoordinates(); finish();
    status.textContent = 'Coordinates cleared. You can still type a landmark above.';
  });
  form.addEventListener('submit', event => {
    if (pending) {
      event.preventDefault();
      status.textContent = 'Please wait for the location result, or choose Clear location to send your report without coordinates.';
    }
  });
}

document.querySelectorAll('.print-card').forEach(button => button.addEventListener('click', () => window.print()));

const chatForm = document.querySelector('[data-chat-form]');
if (chatForm) {
  const box = document.getElementById('chat-question');
  document.querySelectorAll('.retry-question').forEach(button => button.addEventListener('click', () => {box.value = button.dataset.question; box.focus();}));
  chatForm.addEventListener('submit', async event => {
    event.preventDefault();
    const button = chatForm.querySelector('button[type=submit]');
    const status = document.getElementById('chat-status');
    button.disabled = true;
    box.readOnly = true;
    status.textContent = 'Finding relevant guidance…';
    try {
      const response = await fetch(chatForm.action, {method:'POST', body:new FormData(chatForm), headers:{Accept:'application/json'}, credentials:'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The message could not be sent.');
      // A hash-only navigation would leave the old transcript on screen.
      window.history.replaceState(null, '', data.url + '#chat-end');
      window.location.reload();
    } catch(error) {
      status.textContent = error.message + ' Your text is still here. If a reply may be in progress, refresh before retrying.';
      button.disabled = false; box.readOnly = false;
    }
  });
}


const photoForm = document.querySelector('[data-photo-form]');
if (photoForm) {
  const button = photoForm.querySelector('button[type=submit]');
  const status = photoForm.querySelector('[data-analysis-status]');
  const purpose = photoForm.querySelector('[name=purpose]');
  const updatePurpose = () => {
    const general = purpose && purpose.value === 'general';
    button.textContent = !purpose || !purpose.value ? 'Continue photo check ↗' : general ? 'Continue general check ↗' : 'Explore visible concern ↗';
    status.querySelector('strong').textContent = general ? 'Saving your photo…' : 'Looking at the photo…';
    status.querySelector('p').textContent = general ? 'Preparing your general check. No disease model is being run.' : 'Comparing patterns with the selected animal model. Please wait.';
  };
  if (purpose) { purpose.addEventListener('change', updatePurpose); updatePurpose(); }
  photoForm.addEventListener('submit', () => {
    button.disabled = true;
    status.hidden = false;
    photoForm.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    button.disabled = false; status.hidden = true;
    photoForm.removeAttribute('aria-busy');
  });
}
document.querySelectorAll('[data-score]').forEach(ring => {
  const score = Number(ring.dataset.score);
  if (!Number.isFinite(score) || score < 0 || score > 100) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const arc = ring.querySelector('.score-arc');
  const label = ring.querySelector('[data-score-value]');
  const start = performance.now();
  function frame(now) {
    const elapsed = Math.min(1, (now-start)/1000);
    const current = score * (1-Math.pow(1-elapsed,3));
    arc.setAttribute('stroke-dashoffset', String(100-current));
    label.textContent = current.toFixed(1)+'%';
    if (elapsed<1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
});
