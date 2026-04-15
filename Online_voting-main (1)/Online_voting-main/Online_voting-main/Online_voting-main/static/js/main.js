// ── Toast Notifications ──────────────────
function showToast(message, type = 'info') {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  toast.className = `${type}`;
  toast.innerHTML = `<span>${icons[type]}</span> ${message}`;
  toast.classList.add('show');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => toast.classList.remove('show'), 3500);
}

// ── Set Button Loading ────────────────────
function setLoading(btn, loading) {
  if (loading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Please wait...`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
    btn.disabled = false;
  }
}

// ── API Helper ────────────────────────────
async function apiPost(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

// ── Form POST Helper ──────────────────────
async function formPost(url, formData) {
  const res = await fetch(url, {
    method: 'POST',
    body: formData
  });
  return res.json();
}
