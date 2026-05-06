// Global escapeHtml
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Toast notification system
const toastContainer = document.createElement('div');
toastContainer.className = 'toast-container';
document.body.appendChild(toastContainer);

function showToast(message, type = 'info', duration = 3000) {
  const toast = document.createElement('div');
  toast.className = `toast ${type} animate-slide-in`;
  const iconMap = { error: 'ph-x-circle', success: 'ph-check-circle', info: 'ph-info' };
  const iconClass = iconMap[type] || iconMap.info;
  toast.innerHTML = `<i class="ph ${iconClass}" style="font-size:18px;flex-shrink:0;"></i><span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(8px)';
    toast.style.transition = 'opacity 250ms, transform 250ms';
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// Global loading overlay
function showLoading(target = document.body, text = '加载中...') {
  const overlay = document.createElement('div');
  overlay.className = 'loading-overlay';
  if (target === document.body) overlay.classList.add('fixed');
  overlay.innerHTML = `<div class="spinner spinner-lg"></div><div style="margin-top:12px;color:var(--text-secondary);font-size:14px;">${escapeHtml(text)}</div>`;
  target.style.position = 'relative';
  target.appendChild(overlay);
  return overlay;
}

function hideLoading(overlay) {
  overlay?.remove();
}

// Empty state helper
function renderEmptyState(message, actionText, actionHref) {
  const div = document.createElement('div');
  div.className = 'empty-state';
  div.innerHTML = `
    <div class="empty-state-icon"><i class="ph ph-chat-circle-dots" style="font-size:56px;"></i></div>
    <h3>${escapeHtml(message)}</h3>
    ${actionText ? `<a href="${actionHref}" class="btn-small primary">${escapeHtml(actionText)}</a>` : ''}
  `;
  return div;
}

// Confirm dialog (replaces native confirm/alert)
function showConfirm(message, onConfirm, onCancel) {
  const backdrop = document.createElement('div');
  backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:2000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);';
  const dialog = document.createElement('div');
  dialog.className = 'auth-box';
  dialog.style.cssText = 'margin:0;max-width:360px;width:90%;animation:fadeIn var(--transition);';
  dialog.innerHTML = `
    <div style="font-size:16px;font-weight:600;margin-bottom:16px;">${escapeHtml(message)}</div>
    <div style="display:flex;gap:8px;justify-content:flex-end;">
      <button class="btn-small" id="confirm-cancel" style="padding:8px 16px;">取消</button>
      <button class="btn-small primary" id="confirm-ok" style="padding:8px 16px;">确定</button>
    </div>
  `;
  backdrop.appendChild(dialog);
  document.body.appendChild(backdrop);

  dialog.querySelector('#confirm-cancel').onclick = () => { backdrop.remove(); onCancel?.(); };
  dialog.querySelector('#confirm-ok').onclick = () => { backdrop.remove(); onConfirm?.(); };
  backdrop.onclick = (e) => { if (e.target === backdrop) { backdrop.remove(); onCancel?.(); }};
}

// Throttle utility
function throttle(fn, wait) {
  let last = 0;
  return function(...args) {
    const now = Date.now();
    if (now - last >= wait) { last = now; fn.apply(this, args); }
  };
}

// Copy to clipboard
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast('已复制到剪贴板', 'success');
  } catch {
    showToast('复制失败', 'error');
  }
}

// Portrait card component (replaces circular avatar icon)
function renderPortrait(avatar, variant = 'full') {
  const name = escapeHtml(avatar?.name || '?');
  const tagline = escapeHtml(avatar?.tagline || avatar?.bio?.slice(0, 24) || avatar?.persona_prompt?.slice(0, 24) || '');
  const era = escapeHtml(avatar?.era || avatar?.style || avatar?.writing_style || '');
  const moodIcon = avatar?.mood_icon || 'ph-moon-stars';
  const portraitUrl = avatar?.portrait_url;
  const initial = name.slice(0, 1);
  const slotBg = portraitUrl ? `style="background-image:url('${portraitUrl}')"` : '';
  const initialEl = portraitUrl ? '' : `<span class="portrait-initial">${initial}</span>`;
  const sizeClass = variant === 'compact' ? 'compact' : variant === 'byline' ? 'byline' : 'full';
  return `
    <article class="portrait-card" data-variant="${sizeClass}" data-id="${avatar?.id || ''}">
      <div class="portrait-frame">
        <div class="portrait-slot" ${slotBg}>${initialEl}</div>
        ${variant === 'full' ? `<i class="ph-duotone ${moodIcon} portrait-mood"></i>` : ''}
      </div>
      ${variant !== 'icon' ? `
        <div class="portrait-meta">
          <h3 class="portrait-name">${name}</h3>
          ${variant === 'full' && tagline ? `<p class="portrait-tagline">${tagline}</p>` : ''}
          ${variant === 'full' && era ? `<div class="portrait-era"><span class="kicker">${era}</span></div>` : ''}
        </div>` : ''}
    </article>
  `;
}

// Backward-compatible shim for circular avatar icon
function renderAvatarIcon(name, id, size = 40) {
  return renderPortrait({ name, id }, size <= 32 ? 'icon' : 'byline');
}

// Throttle helper
function throttle(fn, ms) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= ms) { last = now; fn(...args); }
  };
}
