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
  { id: 'dashboard', label: '驾驶舱', href: '/static/pages/dashboard.html', icon: 'ph-lightning' },
];

// === Theme: 墨夜/纸白 ===
const THEME_KEY = 'ng-theme';
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  applyTheme(theme);
}
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
}
function themeToggleHTML() {
  return `<button class="theme-toggle" onclick="toggleTheme()" title="切换主题" aria-label="切换主题">
    <i class="ph ph-moon-stars"></i><i class="ph ph-sun-dim"></i>
  </button>`;
}

// Run theme init as early as possible to avoid flash-of-wrong-theme
initTheme();

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
        <a href="/static/pages/settings.html" style="display:flex;align-items:center;gap:6px;color:inherit;text-decoration:none;flex:1;min-width:0;">
          <i class="ph ph-user" style="color:var(--text-tertiary);"></i>
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(currentUser?.nickname || currentUser?.username || '')}</span>
        </a>
        ${themeToggleHTML()}
        <button onclick="logout()">退出</button>
      `;
    }
    return;
  }

  const nav = document.createElement('nav');
  nav.className = 'app-nav';
  nav.innerHTML = `
    <a href="/static/pages/chat.html" class="nav-brand">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" style="vertical-align:middle;color:var(--primary);" role="img" aria-label="书突"><rect x="1.5" y="1.5" width="21" height="21" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><text x="12" y="16.5" font-family="'LXGW WenKai','Songti SC','STSong',serif" font-weight="700" font-size="13" fill="currentColor" text-anchor="middle">书</text></svg>
      <span>书突</span>
    </a>
    <span class="nav-rule"></span>
    ${NAV_PAGES.map(p => `<a href="${p.href}" class="nav-link ${p.id === page ? 'active' : ''}"><i class="ph ${p.icon}"></i><span>${p.label}</span></a>`).join('')}
    <span class="nav-rule"></span>
    <div class="nav-user">
      <a href="/static/pages/settings.html">
        <i class="ph ph-user" style="color:var(--text-tertiary);"></i>
        <span>${escapeHtml(currentUser?.nickname || currentUser?.username || '')}</span>
      </a>
      ${themeToggleHTML()}
      <button onclick="logout()">退出</button>
    </div>
  `;
  document.body.insertBefore(nav, document.body.firstChild);
}

// === Scroll reveal — IntersectionObserver-driven .reveal opt-in ===
function initScrollReveal() {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('is-visible'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('is-visible');
        io.unobserve(e.target);
      }
    });
  }, { rootMargin: '0px 0px -60px 0px', threshold: 0.05 });

  const observe = (root) => root.querySelectorAll('.reveal:not(.is-visible)').forEach(el => io.observe(el));
  observe(document);

  // Re-scan when client-side renders inject new cards (post-list, avatar-grid, etc.)
  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      m.addedNodes.forEach(n => {
        if (n.nodeType !== 1) return;
        if (n.classList && n.classList.contains('reveal')) io.observe(n);
        if (n.querySelectorAll) observe(n);
      });
    }
  });
  mo.observe(document.body, { childList: true, subtree: true });
}

document.addEventListener('DOMContentLoaded', async () => {
  initScrollReveal();
  const page = document.body.dataset.page;
  if (page && page !== 'login') {
    await getMe();
    renderNav();
  }
});
