let currentPage = 1;
let loading = false;
let hasMore = true;

async function init() {
  const user = await getMe();
  if (!user) return;
  await loadPosts();
  window.addEventListener('scroll', onScroll);
}

async function loadPosts() {
  if (loading || !hasMore) return;
  loading = true;
  document.getElementById('loading').style.display = 'block';
  try {
    const posts = await get(`/api/posts?page=${currentPage}&limit=20`);
    const container = document.getElementById('post-list');
    if (!posts || posts.length === 0) {
      hasMore = false;
      if (currentPage === 1) container.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px;">暂无内容，去和助手聊聊吧</div>';
    } else {
      posts.forEach(p => container.appendChild(renderPostCard(p)));
      currentPage++;
    }
  } catch (err) {
    console.error(err);
  }
  loading = false;
  document.getElementById('loading').style.display = hasMore ? 'block' : 'none';
}

function renderPostCard(p) {
  const div = document.createElement('div');
  div.className = 'post-card';
  div.innerHTML = `
    <div class="meta">
      <strong>${escapeHtml(p.author_name || '用户' + p.author_id)}</strong>
      <span>${new Date(p.created_at).toLocaleString()}</span>
    </div>
    <div class="content">${escapeHtml(p.content)}</div>
    ${p.tags ? `<div class="tags">${JSON.parse(p.tags || '[]').map(t => `<span>${escapeHtml(t)}</span>`).join('')}</div>` : ''}
    <div class="actions-bar">
      <span onclick="likePost(${p.id}, this)">♡ 点赞</span>
      <span onclick="location.href='/static/pages/post.html?id=${p.id}'">💬 评论</span>
    </div>
  `;
  return div;
}

async function likePost(id, el) {
  try {
    const res = await post(`/api/posts/${id}/like`, {});
    el.textContent = res.liked ? '♥ 已赞 ' + res.like_count : '♡ 点赞 ' + res.like_count;
  } catch (err) {
    alert(err.message);
  }
}

function onScroll() {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
    loadPosts();
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

init();
