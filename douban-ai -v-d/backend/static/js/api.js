const API_BASE = '';

async function api(path, options = {}) {
  const url = API_BASE + path;
  const res = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (res.status === 401) {
    location.href = '/static/pages/login.html';
    return null;
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function post(path, body) {
  return api(path, { method: 'POST', body: JSON.stringify(body) });
}

async function get(path) {
  return api(path, { method: 'GET' });
}

async function del(path) {
  return api(path, { method: 'DELETE' });
}
