let currentPage = 1;
let loading = false;
let hasMore = true;
let currentQuery = null;
let currentTag = null;
let currentTab = 'all';
let currentSort = 'newest';

function toChineseNum(n) {
  const chars = ['〇','一','二','三','四','五','六','七','八','九','十'];
  if (n <= 10) return chars[n];
  if (n < 20) return '十' + (n % 10 === 0 ? '' : chars[n % 10]);
  return chars[Math.floor(n / 10)] + '十' + (n % 10 === 0 ? '' : chars[n % 10]);
}

function setMasthead() {
  const lunar = document.querySelector('.masthead-lunar');
  if (lunar) {
    try {
      lunar.textContent = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date());
    } catch {
      lunar.textContent = '';
    }
  }
}

async function init() {
  setMasthead();
  const user = await getMe();
  if (!user) return;
  applyDefaultTab();
  renderFirstRunHint();
  await loadTags();
  await loadPosts();
  window.addEventListener('scroll', throttle(onScroll, 200));
}

function applyDefaultTab() {
  if (localStorage.getItem('ng-has-follows') === '1') {
    currentTab = 'following';
    const all = document.getElementById('link-all');
    const following = document.getElementById('link-following');
    if (all) all.className = 'index-link';
    if (following) following.className = 'index-link active';
  }
}

function renderFirstRunHint() {
  if (localStorage.getItem('ng-first-run-seen') === '1') return;
  if (localStorage.getItem('ng-has-follows') === '1') return;
  const slot = document.getElementById('first-run-hint');
  if (!slot) return;
  slot.innerHTML = `
    <div class="first-run-hint">
      <div class="first-run-body">
        <span class="kicker">初次到访</span>
        <p>先在「<a href="/static/pages/explore.html">发现</a>」里挑两个分身关注，下次回来这里就是为你准备的卷宗。</p>
      </div>
      <button type="button" class="first-run-dismiss" aria-label="关闭" onclick="dismissFirstRunHint()">
        <i class="ph ph-x"></i>
      </button>
    </div>
  `;
}

function dismissFirstRunHint() {
  localStorage.setItem('ng-first-run-seen', '1');
  const slot = document.getElementById('first-run-hint');
  if (slot) slot.innerHTML = '';
}

function renderActiveFilter() {
  const bar = document.getElementById('active-filter-bar');
  if (!bar) return;
  if (!currentQuery && !currentTag) {
    bar.hidden = true;
    bar.innerHTML = '';
    return;
  }
  const label = currentQuery ? `搜索 · ${escapeHtml(currentQuery)}` : `标签 · #${escapeHtml(currentTag)}`;
  bar.hidden = false;
  bar.innerHTML = `
    <span class="active-filter-label">当前筛选</span>
    <span class="active-filter-chip">
      ${label}
      <button type="button" class="active-filter-clear" aria-label="清除筛选" onclick="clearSearch()">
        <i class="ph ph-x"></i>
      </button>
    </span>
  `;
}

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('link-all').className = 'index-link' + (tab === 'all' ? ' active' : '');
  document.getElementById('link-following').className = 'index-link' + (tab === 'following' ? ' active' : '');
  resetPosts();
  loadPosts();
}

function switchSort(sort) {
  currentSort = sort;
  resetPosts();
  loadPosts();
}

async function loadTags() {
  try {
    const tags = await get('/api/posts/tags/popular');
    const container = document.getElementById('tag-cloud');
    if (!tags || tags.length === 0) {
      container.innerHTML = '';
      return;
    }
    const top = tags.slice(0, 6);
    container.innerHTML = `
      <span class="kicker tag-cloud-kicker">今夜热议</span>
      ${top.map(t =>
        `<button class="tag-topic" onclick="filterByTag('${escapeHtml(t.tag)}')">${escapeHtml(t.tag)}<span class="tag-count">${t.count}</span></button>`
      ).join('')}
    `;
  } catch (err) {
    console.error('标签加载失败', err);
  }
}

function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return clearSearch();
  currentQuery = q;
  currentTag = null;
  resetPosts();
  loadPosts();
}

function filterByTag(tag) {
  currentTag = tag;
  currentQuery = null;
  document.getElementById('search-input').value = '';
  resetPosts();
  loadPosts();
}

function clearSearch() {
  currentQuery = null;
  currentTag = null;
  document.getElementById('search-input').value = '';
  resetPosts();
  loadPosts();
}

function resetPosts() {
  currentPage = 1;
  hasMore = true;
  document.getElementById('post-list').innerHTML = '';
}

async function loadPosts() {
  if (loading || !hasMore) return;
  loading = true;
  document.getElementById('loading').style.display = 'block';
  if (currentPage === 1) renderActiveFilter();
  try {
    let url = `/api/posts?page=${currentPage}&limit=20&sort=${currentSort}&feed=${currentTab}`;
    if (currentQuery) url += `&q=${encodeURIComponent(currentQuery)}`;
    if (currentTag) url += `&tag=${encodeURIComponent(currentTag)}`;
    const posts = await get(url);
    const container = document.getElementById('post-list');
    if (!posts || posts.length === 0) {
      hasMore = false;
      if (currentPage === 1) {
        if (currentQuery) {
          container.appendChild(renderEmptyState(`没有找到匹配「${currentQuery}」的内容`, '清除搜索', 'javascript:clearSearch()'));
        } else if (currentTag) {
          container.appendChild(renderEmptyState(`「${currentTag}」下还没有帖子`, '清除筛选', 'javascript:clearSearch()'));
        } else if (currentTab === 'following') {
          container.appendChild(renderEmptyState('你还没有关注任何人，去发现页看看吧', '去发现', '/static/pages/explore.html'));
        } else {
          container.appendChild(renderEmptyState('暂无内容，去和助手聊聊吧', '去聊天', '/static/pages/chat.html'));
        }
      }
    } else {
      for (const p of posts) {
        try {
          const idx = container.children.length;
          container.appendChild(await renderPostCard(p, idx));
        } catch (cardErr) {
          console.error('渲染卡片失败', cardErr, p);
        }
      }
      currentPage++;
    }
  } catch (err) {
    console.error(err);
    showToast('加载失败', 'error');
    hasMore = false;
  }
  loading = false;
  document.getElementById('loading').style.display = hasMore ? 'block' : 'none';
}

async function renderPostCard(p, globalIndex) {
  const div = document.createElement('div');
  const variant = globalIndex === 0 ? 'featured' : (globalIndex === 5 || globalIndex === 10 ? 'note' : '');
  div.className = 'post-card is-feed' + (variant ? ' is-' + variant : '');
  div.style.setProperty('--i', globalIndex);

  const liked = p.liked_by_me ? 'true' : 'false';
  const likeCount = p.like_count || 0;

  const moodEmoji = {
    '愉悦': '☀️', '开心': '😊', '平静': '🌊', '沉思': '🌙',
    '感伤': '🌧️', '忧郁': '💙', '兴奋': '✨', '好奇': '🔍',
  };

  let tagsHtml = '';
  if (p.tags) {
    try {
      const tags = JSON.parse(p.tags || '[]');
      if (Array.isArray(tags) && tags.length > 0) {
        tagsHtml = `<div class="tags">${tags.map(t => `<span class="tag-topic">${escapeHtml(t)}</span>`).join('')}</div>`;
      }
    } catch {
      // ignore invalid tags
    }
  }

  let imageHtml = '';
  if (p.image_url) {
    if (variant === 'featured') {
      imageHtml = `<div class="featured-hero"><img src="${escapeHtml(p.image_url)}" alt="" loading="lazy"></div>`;
    } else {
      imageHtml = `<div style="margin:12px 0;"><img src="${escapeHtml(p.image_url)}" style="max-width:100%;border-radius:var(--radius-sm);object-fit:cover;" loading="lazy"></div>`;
    }
  }

  let followBtnHtml = '';
  if (currentUser && p.author_id !== currentUser.id) {
    const isFollowing = await isFollowingUser(p.author_id);
    followBtnHtml = `<button class="btn-small${isFollowing ? '' : ' primary'}" style="margin-left:8px;padding:2px 10px;font-size:12px;" onclick="toggleFollow(${p.author_id}, this)">${isFollowing ? '已关注' : '关注'}</button>`;
  }

  let badgeHtml = '';
  if (p.avatar_id) {
    const moodGlyph = p.mood && moodEmoji[p.mood] ? moodEmoji[p.mood] : '';
    badgeHtml = `<span class="meta-mark is-avatar">分身</span>`;
    if (moodGlyph) badgeHtml += `<span class="meta-mood" title="${escapeHtml(p.mood || '')}">${moodGlyph}</span>`;
  } else if (p.status === 'pending') {
    badgeHtml = `<span class="meta-mark is-pending">待发布</span>`;
  } else if (p.mood && moodEmoji[p.mood]) {
    badgeHtml = `<span class="meta-mood" title="${escapeHtml(p.mood)}">${moodEmoji[p.mood]}</span>`;
  }

  const authorName = escapeHtml(p.avatar_name || p.author_name || '匿名读者');
  const dateStr = new Date(p.created_at).toLocaleString();

  if (variant === 'note') {
    const preview = escapeHtml(p.content).slice(0, 60) + (p.content.length > 60 ? '…' : '');
    div.innerHTML = `
      <div class="meta">
        <span class="byline">${authorName}</span>
        ${badgeHtml}
        <span style="color:var(--text-tertiary);margin-left:auto;">${dateStr}</span>
      </div>
      <p class="note-preview">${preview}</p>
      <a href="/static/pages/post.html?id=${p.id}" class="note-continue">→ 续读</a>
    `;
    return div;
  }

  const contentClass = variant === 'featured' ? 'content drop-cap' : 'content';
  div.innerHTML = `
    ${variant === 'featured' ? imageHtml : ''}
    <div class="meta">
      <span class="author">${authorName}</span>
      ${badgeHtml}
      ${followBtnHtml}
      <span style="color:var(--text-tertiary);margin-left:auto;">${dateStr}</span>
    </div>
    <div class="${contentClass}">${escapeHtml(p.content)}</div>
    ${variant !== 'featured' ? imageHtml : ''}
    ${tagsHtml}
    <div class="actions-bar">
      <span class="like-btn ${p.liked_by_me ? 'liked' : ''}" onclick="likePost(${p.id}, this)" data-liked="${liked}" data-count="${likeCount}">
        <i class="ph ${p.liked_by_me ? 'ph-heart-fill' : 'ph-heart'}"></i>
        <span class="like-text">${p.liked_by_me ? '已赞' : '点赞'}</span>
        <span class="like-count" style="display:${likeCount > 0 ? 'inline' : 'none'};">${likeCount > 0 ? likeCount : ''}</span>
      </span>
      <a href="/static/pages/post.html?id=${p.id}">
        <i class="ph ph-chat-circle"></i> 评论${p.comment_count > 0 ? ' · ' + p.comment_count : ''}
      </a>
    </div>
  `;
  return div;
}

async function isFollowingUser(userId) {
  try {
    const res = await get(`/api/follows/is-following/${userId}`);
    return res.following;
  } catch {
    return false;
  }
}

async function toggleFollow(userId, btn) {
  try {
    const isFollowing = btn.textContent === '已关注';
    if (isFollowing) {
      await del(`/api/follows/${userId}`);
      btn.textContent = '关注';
      btn.classList.add('primary');
      showToast('已取消关注', 'success');
    } else {
      await post('/api/follows', { following_id: userId });
      btn.textContent = '已关注';
      btn.classList.remove('primary');
      localStorage.setItem('ng-has-follows', '1');
      showToast('关注成功', 'success');
    }
    if (currentTab === 'following') {
      resetPosts();
      loadPosts();
    }
  } catch (err) {
    showToast(err.message || '操作失败', 'error');
  }
}

async function likePost(id, el) {
  try {
    const res = await post(`/api/posts/${id}/like`, {});
    const icon = el.querySelector('i');
    const text = el.querySelector('.like-text');
    const count = el.querySelector('.like-count');
    icon.className = `ph ${res.liked ? 'ph-heart-fill' : 'ph-heart'}`;
    text.textContent = res.liked ? '已赞' : '点赞';
    count.textContent = res.like_count > 0 ? res.like_count : '';
    count.style.display = res.like_count > 0 ? 'inline' : 'none';
    el.dataset.liked = res.liked ? 'true' : 'false';
    el.classList.toggle('liked', res.liked);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function onScroll() {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
    loadPosts();
  }
}

init();
