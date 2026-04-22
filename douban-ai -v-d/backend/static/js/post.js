const params = new URLSearchParams(location.search);
const postId = params.get('id');

async function init() {
  if (!postId) return location.href = '/static/pages/community.html';
  const user = await getMe();
  if (!user) return;
  await loadPost();
  await loadComments();
}

async function loadPost() {
  try {
    const p = await get(`/api/posts/${postId}`);
    const container = document.getElementById('post-detail');
    container.innerHTML = `
      <div class="post-card">
        <div class="meta">
          <strong>${escapeHtml(p.author_name || '用户' + p.author_id)}</strong>
          <span>${new Date(p.created_at).toLocaleString()}</span>
        </div>
        <div class="content">${escapeHtml(p.content)}</div>
        ${p.tags ? `<div class="tags">${JSON.parse(p.tags || '[]').map(t => `<span>${escapeHtml(t)}</span>`).join('')}</div>` : ''}
        <div class="actions-bar">
          <span onclick="likePost(this)">♡ 点赞</span>
        </div>
      </div>
    `;
  } catch (err) {
    document.getElementById('post-detail').innerHTML = '<div style="color:#c33;">加载失败</div>';
  }
}

async function loadComments() {
  try {
    const comments = await get(`/api/comments/posts/${postId}/comments`);
    const container = document.getElementById('comments');
    container.innerHTML = '<h3 style="font-size:16px;margin-bottom:12px;">评论</h3>';
    if (!comments || comments.length === 0) {
      container.innerHTML += '<div style="color:var(--muted);">暂无评论</div>';
      return;
    }
    comments.forEach(c => {
      const div = document.createElement('div');
      div.style = 'padding:12px 0;border-bottom:1px solid var(--border);';
      div.innerHTML = `
        <div style="font-size:13px;color:var(--muted);margin-bottom:4px;">${escapeHtml(c.author_name || '用户' + c.author_id)} · ${new Date(c.created_at).toLocaleString()}</div>
        <div>${escapeHtml(c.content)}</div>
      `;
      container.appendChild(div);
    });
  } catch (err) {
    console.error(err);
  }
}

async function postComment() {
  const input = document.getElementById('comment-input');
  const text = input.value.trim();
  if (!text) return;
  try {
    await post(`/api/comments/posts/${postId}/comments`, { content: text });
    input.value = '';
    await loadComments();
  } catch (err) {
    alert(err.message);
  }
}

async function likePost(el) {
  try {
    const res = await post(`/api/posts/${postId}/like`, {});
    el.textContent = res.liked ? '♥ 已赞 ' + res.like_count : '♡ 点赞 ' + res.like_count;
  } catch (err) {
    alert(err.message);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

init();
