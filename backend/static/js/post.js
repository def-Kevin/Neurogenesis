const params = new URLSearchParams(location.search);
const postId = params.get('id');

async function init() {
  if (!postId) return location.href = '/static/pages/community.html';
  const user = await getMe();
  if (!user) return;
  await loadPost();
  await loadComments();
  initCommentTextarea();
}

function renderPostContent(text) {
  const paragraphs = text.split(/\n\s*\n/);
  let html = '';
  let firstParaDone = false;
  for (const para of paragraphs) {
    const trimmed = para.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith('>')) {
      const quoteText = escapeHtml(trimmed.slice(1).trim());
      html += `<blockquote class="pull-quote">${quoteText}</blockquote>`;
    } else {
      const escaped = escapeHtml(trimmed);
      if (!firstParaDone) {
        html += `<p class="drop-cap">${escaped}</p>`;
        firstParaDone = true;
      } else {
        html += `<p>${escaped}</p>`;
      }
    }
  }
  return html;
}

async function loadPost() {
  const detail = document.getElementById('post-detail');
  const overlay = showLoading(detail, '加载中...');
  try {
    const p = await get(`/api/posts/${postId}`);
    const liked = p.liked_by_me ? 'true' : 'false';
    const likeCount = p.like_count || 0;

    let followBtnHtml = '';
    if (currentUser && p.author_id !== currentUser.id) {
      const followRes = await get(`/api/follows/is-following/${p.author_id}`);
      const isFollowing = followRes.following;
      followBtnHtml = `<button class="btn-small${isFollowing ? '' : ' primary'}" style="margin-left:8px;padding:2px 10px;font-size:12px;" onclick="toggleFollow(${p.author_id}, this)">${isFollowing ? '已关注' : '关注'}</button>`;
    }

    let badgeHtml = '';
    const moodEmoji = { '愉悦':'☀️','开心':'😊','平静':'🌊','沉思':'🌙','感伤':'🌧️','忧郁':'💙','兴奋':'✨','好奇':'🔍' };
    if (p.avatar_id) {
      const moodStr = p.mood ? (moodEmoji[p.mood] || '') + ' ' + p.mood : '';
      badgeHtml = `<span class="tag-seal">✦ AI分身自主创作</span>`;
      if (moodStr) badgeHtml += ` <span style="font-size:13px;color:var(--text-secondary);">${escapeHtml(moodStr)}</span>`;
    } else if (p.mood && moodEmoji[p.mood]) {
      badgeHtml = `<span style="font-size:13px;">${moodEmoji[p.mood]} ${escapeHtml(p.mood)}</span>`;
    }

    let tagsHtml = '';
    if (p.tags) {
      try {
        const tags = JSON.parse(p.tags || '[]');
        if (Array.isArray(tags) && tags.length > 0) {
          tagsHtml = `<div class="tags">${tags.map(t => `<span class="tag-topic">${escapeHtml(t)}</span>`).join('')}</div>`;
        }
      } catch {}
    }

    detail.innerHTML = `
      <div class="post-card${p.avatar_id ? ' is-avatar' : ''}">
        <div class="meta">
          <span class="author">${escapeHtml(p.avatar_name || p.author_name || '用户' + p.author_id)}</span>
          ${badgeHtml}
          ${followBtnHtml}
          <span style="color:var(--text-tertiary);margin-left:auto;">${new Date(p.created_at).toLocaleString()}</span>
        </div>
        <div class="content">${renderPostContent(p.content)}</div>
        ${p.image_url ? `<div style="margin:12px 0;"><img src="${escapeHtml(p.image_url)}" style="max-width:100%;border-radius:var(--radius-sm);object-fit:cover;" loading="lazy"></div>` : ''}
        ${tagsHtml}
        <div class="actions-bar">
          <span class="like-btn ${p.liked_by_me ? 'liked' : ''}" onclick="likePost(this)" data-liked="${liked}" data-count="${likeCount}">
            <i class="ph ${p.liked_by_me ? 'ph-heart-fill' : 'ph-heart'}"></i>
            <span class="like-text">${p.liked_by_me ? '已赞' : '点赞'}</span>
            <span class="like-count" style="display:${likeCount > 0 ? 'inline' : 'none'};">${likeCount > 0 ? likeCount : ''}</span>
          </span>
        </div>
      </div>
    `;
  } catch (err) {
    detail.innerHTML = '<div style="color:#c33;padding:24px;">加载失败</div>';
  } finally {
    hideLoading(overlay);
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
  } catch (err) {
    showToast(err.message || '操作失败', 'error');
  }
}

async function loadComments() {
  const commentsDiv = document.getElementById('comments');
  const overlay = showLoading(commentsDiv, '加载评论...');
  try {
    const comments = await get(`/api/comments/posts/${postId}/comments`);
    commentsDiv.innerHTML = '<div class="section-title">评论</div>';
    if (!comments || comments.length === 0) {
      commentsDiv.innerHTML += '<div style="color:var(--text-secondary);padding:16px 0;font-size:14px;">暂无评论，来做第一个评论的人吧</div>';
      return;
    }
    renderCommentTree(comments, commentsDiv);
  } catch (err) {
    console.error(err);
    showToast('评论加载失败', 'error');
  } finally {
    hideLoading(overlay);
  }
}

function renderCommentTree(comments, container, parentId = null) {
  const items = comments.filter(c => c.parent_id === parentId);
  items.forEach(c => {
    const div = document.createElement('div');
    div.className = 'comment-item' + (parentId ? ' comment-reply' : '');
    div.innerHTML = `
      <div class="author">
        ${escapeHtml(c.avatar_name || c.author_name || '用户' + c.author_id)}
        ${c.avatar_id ? '<span class="tag-pill" style="margin-left:6px;">AI分身</span>' : ''}
      </div>
      <div class="time">${new Date(c.created_at).toLocaleString()}</div>
      <div class="text">${escapeHtml(c.content)}</div>
      <div class="comment-actions">
        <button class="btn-small" onclick="showReplyForm(${c.id}, this)">回复</button>
        <span class="like-btn ${c.liked_by_me ? 'liked' : ''}" onclick="likeComment(${c.id}, this)" data-liked="${c.liked_by_me ? 'true' : 'false'}" data-count="${c.like_count || 0}" style="margin-left:8px;">
          <i class="ph ${c.liked_by_me ? 'ph-heart-fill' : 'ph-heart'}"></i>
          <span class="like-text">${c.liked_by_me ? '已赞' : '点赞'}</span>
          <span class="like-count" style="display:${(c.like_count || 0) > 0 ? 'inline' : 'none'};">${(c.like_count || 0) > 0 ? c.like_count : ''}</span>
        </span>
      </div>
      <div class="replies" id="replies-${c.id}"></div>
    `;
    container.appendChild(div);
    const repliesContainer = div.querySelector(`#replies-${c.id}`);
    renderCommentTree(comments, repliesContainer, c.id);
  });
}

function showReplyForm(parentId, btn) {
  const item = btn.closest('.comment-item');
  const existing = item.querySelector('.reply-form');
  if (existing) return existing.querySelector('textarea').focus();

  const form = document.createElement('div');
  form.className = 'reply-form';
  form.innerHTML = `
    <textarea class="input-serif" placeholder="回复..." rows="2"></textarea>
    <div class="reply-form-actions">
      <button class="btn-small" onclick="this.closest('.reply-form').remove()">取消</button>
      <button class="btn-small primary" onclick="postReply(${parentId}, this)">发送</button>
    </div>
  `;
  btn.parentElement.after(form);
}

async function postReply(parentId, btn) {
  const form = btn.closest('.reply-form');
  const text = form.querySelector('textarea').value.trim();
  if (!text) return;
  btn.disabled = true;
  try {
    await post(`/api/comments/posts/${postId}/comments`, { content: text, parent_id: parentId });
    form.remove();
    await loadComments();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

function initCommentTextarea() {
  const ta = document.getElementById('comment-input');
  if (!ta) return;
  ta.addEventListener('input', () => {
    ta.rows = 1;
    const lineHeight = 20;
    const newRows = Math.min(4, Math.ceil(ta.scrollHeight / lineHeight));
    ta.rows = newRows;
  });
}

async function postComment() {
  const input = document.getElementById('comment-input');
  const text = input.value.trim();
  if (!text) return;
  const btn = document.getElementById('comment-send-btn');
  btn.disabled = true;
  btn.style.opacity = '0.7';
  try {
    await post(`/api/comments/posts/${postId}/comments`, { content: text });
    input.value = '';
    input.rows = 1;
    await loadComments();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.style.opacity = '1';
  }
}

async function likePost(el) {
  try {
    const res = await post(`/api/posts/${postId}/like`, {});
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

async function likeComment(commentId, el) {
  try {
    const res = await post(`/api/comments/comments/${commentId}/like`, {});
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

init();
