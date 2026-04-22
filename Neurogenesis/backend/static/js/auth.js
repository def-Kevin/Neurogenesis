let currentUser = null;

async function getMe() {
  try {
    currentUser = await get('/api/auth/me');
    return currentUser;
  } catch {
    currentUser = null;
    return null;
  }
}

async function logout() {
  await post('/api/auth/logout', {});
  location.href = '/static/pages/login.html';
}

const NAV_PAGES = [
  { id: 'chat', label: '助手', href: '/static/pages/chat.html', icon: 'ph-chat-circle-text' },
  { id: 'community', label: '社区', href: '/static/pages/community.html', icon: 'ph-users' },
  { id: 'follows', label: '关注', href: '/static/pages/follows.html', icon: 'ph-heart' },
  { id: 'avatars', label: '分身', href: '/static/pages/avatars.html', icon: 'ph-user-circle' },
  { id: 'explore', label: '发现', href: '/static/pages/explore.html', icon: 'ph-compass' },
];

function renderNav() {
  const existing = document.querySelector('.app-nav');
  if (existing) existing.remove();

  const page = document.body.dataset.page;
  if (!page || page === 'login') return;

  // Chat page: sidebar has its own nav links; only fill user info here
  if (page === 'chat') {
    const sidebarUser = document.getElementById('sidebar-user');
    if (sidebarUser) {
      sidebarUser.innerHTML = `
        <a href="/static/pages/settings.html" style="display:flex;align-items:center;gap:6px;color:inherit;text-decoration:none;">
          <i class="ph ph-user" style="color:var(--text-tertiary);"></i>
          <span>${escapeHtml(currentUser?.nickname || currentUser?.username || '')}</span>
        </a>
        <button onclick="logout()">退出</button>
      `;
    }
    return;
  }

  const nav = document.createElement('nav');
  nav.className = 'app-nav';
  nav.innerHTML = `
    <a href="/static/pages/chat.html" class="nav-brand">神经发生</a>
    ${NAV_PAGES.map(p => `<a href="${p.href}" class="nav-link ${p.id === page ? 'active' : ''}"><i class="ph ${p.icon}"></i> ${p.label}</a>`).join('')}
    <div class="nav-spacer"></div>
    <div class="nav-user">
      <a href="/static/pages/settings.html" style="display:flex;align-items:center;gap:6px;color:inherit;text-decoration:none;">
        <i class="ph ph-user" style="color:var(--text-tertiary);"></i>
        <span>${escapeHtml(currentUser?.nickname || currentUser?.username || '')}</span>
      </a>
      <button onclick="logout()">退出</button>
    </div>
  `;
  document.body.insertBefore(nav, document.body.firstChild);
}

document.addEventListener('DOMContentLoaded', async () => {
  const page = document.body.dataset.page;
  if (page && page !== 'login') {
    await getMe();
    renderNav();
  }
});
