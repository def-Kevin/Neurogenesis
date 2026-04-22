async function getMe() {
  try {
    return await get('/api/auth/me');
  } catch {
    return null;
  }
}

async function logout() {
  await post('/api/auth/logout', {});
  location.href = '/static/pages/login.html';
}
