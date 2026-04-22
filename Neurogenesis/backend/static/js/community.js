let currentPage = 1;
let loading = false;
let hasMore = true;
let currentQuery = null;
let currentTag = null;
let currentTab = 'all';
let currentSort = 'newest';

async function init() {
  const user = await getMe();
  if (!user) return;
  await loadTags();
  await loadPosts();
  window.addEventListener('scroll', throttle(onScroll, 200));
}

function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-all').className = 'btn-small' + (tab === 'all' ? ' primary' : '');
  document.getElementById('tab-all').style.fontWeight = tab === 'all' ? '600' : '';
  document.getElementById('tab-following').className = 'btn-small' + (tab === 'following' ? ' primary' : '');
  document.getElementById('tab-following').style.fontWeight = tab === 'following' ? '600' : '';
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
    if (!tags || tags.length === 0) return;
    container.innerHTML = tags.map(t =>
      `<button class="btn-small" style="padding:4px 12px;font-size:13px;" onclick="filterByTag('${escapeHtml(t.tag)}')">${escapeHtml(t.tag)} · ${t.count}</button>`
    ).join('');
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
  try {
    let url = `/api/posts?page=${currentPage}&limit=20&sort=${currentSort}&feed=${currentTab}`;
    if (currentQuery) url += `&q=${encodeURIComponent(currentQuery)}`;
    if (currentTag) url += `&tag=${encodeURIComponent(currentTag)}`;
    const posts = await get(url);
    const container = document.getElementById('post-list');
    if (!posts || posts.length === 0) {
      hasMore = false;
      if (currentPage === 1) {
        if (currentTab === 'following') {
          container.appendChild(renderEmptyState('你还没有关注任何人，去发现页看看吧', '去发现', '/static/pages/explore.html'));
        } else {
          container.appendChild(renderEmptyState('暂无内容，去和助手聊聊吧', '去聊天', '/static/pages/chat.html'));
        }
      }
    } else {
      for (const p of posts) {
        try {
          container.appendChild(await renderPostCard(p));
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

async function renderPostCard(p) {
  const div = document.createElement('div');
  div.className = 'post-card';
  const liked = p.liked_by_me ? 'true' : 'false';
  const likeCount = p.like_count || 0;

  let tagsHtml = '';
  if (p.tags) {
    try {
      const tags = JSON.parse(p.tags || '[]');
      if (Array.isArray(tags) && tags.length > 0) {
        tagsHtml = `<div class="tags">${tags.map(t => `<span>${escapeHtml(t)}</span>`).join('')}</div>`;
      }
    } catch {
      // ignore invalid tags
    }
  }

  let imageHtml = '';
  if (p.image_url) {
    imageHtml = `<div style="margin:12px 0;"><img src="${escapeHtml(p.image_url)}" style="max-width:100%;border-radius:var(--radius-sm);object-fit:cover;" loading="lazy"></div>`;
  }

  let followBtnHtml = '';
  if (currentUser && p.author_id !== currentUser.id) {
    const isFollowing = await isFollowingUser(p.author_id);
    followBtnHtml = `<button class="btn-small${isFollowing ? '' : ' primary'}" style="margin-left:8px;padding:2px 10px;font-size:12px;" onclick="toggleFollow(${p.author_id}, this)">${isFollowing ? '已关注' : '关注'}</button>`;
  }

  let badgeHtml = '';
  if (p.avatar_id) {
    badgeHtml = `<span class="badge">AI分身</span>`;
  } else if (p.status === 'pending') {
    badgeHtml = `<span class="badge">待发布</span>`;
  }

  div.innerHTML = `
    <div class="meta">
      <span class="author">${escapeHtml(p.avatar_name || p.author_name || '用户' + p.author_id)}</span>
      ${badgeHtml}
      ${followBtnHtml}
      <span style="color:var(--text-tertiary);margin-left:auto;">${new Date(p.created_at).toLocaleString()}</span>
    </div>
    <div class="content">${escapeHtml(p.content)}</div>
    ${imageHtml}
    ${tagsHtml}
    <div class="actions-bar">
      <span class="like-btn ${p.liked_by_me ? 'liked' : ''}" onclick="likePost(${p.id}, this)" data-liked="${liked}" data-count="${likeCount}">
        <i class="ph ${p.liked_by_me ? 'ph-heart-fill' : 'ph-heart'}"></i>
        <span class="like-text">${p.liked_by_me ? '已赞' : '点赞'}</span>
        <span class="like-count" style="display:${likeCount > 0 ? 'inline' : 'none'};">${likeCount > 0 ? likeCount : ''}</span>
      </span>
      <a href="/static/pages/post.html?id=${p.id}">
        <i class="ph ph-chat-circle"></i> 评论
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
