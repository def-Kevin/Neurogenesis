let currentConvoId = null;
let isStreaming = false;
const urlParams = new URLSearchParams(location.search);
const avatarId = urlParams.get('avatar_id');

async function init() {
  const user = await getMe();
  if (!user) return;
  if (avatarId) {
    document.querySelector('.chat-sidebar').style.display = 'none';
    document.getElementById('chat-header').textContent = '与分身聊天';
    // find or create avatar conversation
    const convos = await get('/api/conversations');
    const existing = (convos || []).find(c => c.avatar_id == avatarId);
    if (existing) {
      selectConvo(existing.id);
    } else {
      const convo = await post('/api/conversations', { avatar_id: parseInt(avatarId) });
      selectConvo(convo.id);
    }
  } else {
    await loadConversations();
    const first = document.querySelector('.convo-item');
    if (first) selectConvo(parseInt(first.dataset.id));
  }
}

async function loadConversations() {
  const list = await get('/api/conversations');
  const container = document.getElementById('convo-list');
  container.innerHTML = '';
  (list || []).forEach(c => {
    const el = document.createElement('div');
    el.className = 'convo-item';
    el.dataset.id = c.id;
    el.innerHTML = `<div class="title">${escapeHtml(c.title || '对话')}</div><div class="preview">${escapeHtml(c.status || '')}</div>`;
    el.onclick = () => selectConvo(c.id);
    container.appendChild(el);
  });
}

async function createConversation() {
  const payload = avatarId ? { avatar_id: parseInt(avatarId) } : {};
  const convo = await post('/api/conversations', payload);
  await loadConversations();
  selectConvo(convo.id);
}

async function selectConvo(id) {
  currentConvoId = id;
  document.querySelectorAll('.convo-item').forEach(el => el.classList.toggle('active', parseInt(el.dataset.id) === id));
  const messages = await get(`/api/conversations/${id}/messages`);
  const container = document.getElementById('chat-messages');
  container.innerHTML = '';
  (messages || []).forEach(m => appendMessage(m.role, m.content));
  scrollToBottom();
}

function appendMessage(role, content) {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  // parse special tags
  let html = escapeHtml(content);

  // draft cards
  html = html.replace(/\[DRAFT\]([\s\S]*?)\[\/DRAFT\]/g, (_, draft) => {
    return `<div class="draft-card"><div style="white-space:pre-wrap;">${escapeHtml(draft.trim())}</div><div class="actions"><button class="btn-small" onclick="editDraft(this)">编辑</button><button class="btn-small primary" onclick="publishDraft(this)">发布</button></div></div>`;
  });

  // rec cards
  html = html.replace(/\[REC\]([^|]+)\|([^|]+)\|([^|]+)\|([^\[]+)\[\/REC\]/g, (_, type, title, creator, reason) => {
    return `<div class="rec-card"><div style="font-weight:600;">${escapeHtml(title)} · ${escapeHtml(creator)}</div><div style="font-size:12px;color:var(--muted);">${escapeHtml(type)}</div><div style="margin-top:4px;">${escapeHtml(reason.trim())}</div><div class="actions"><button class="btn-small">想看</button><button class="btn-small">不感兴趣</button></div></div>`;
  });

  row.innerHTML = `<div class="bubble ${role}">${html}</div>`;
  container.appendChild(row);
  scrollToBottom();
}

function appendStreamingBubble() {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = 'streaming-msg';
  row.innerHTML = '<div class="bubble assistant"><span id="stream-text"></span><span style="animation:blink 1s infinite;">...</span></div>';
  container.appendChild(row);
  scrollToBottom();
  return row;
}

function scrollToBottom() {
  const container = document.getElementById('chat-messages');
  container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !currentConvoId || isStreaming) return;
  input.value = '';
  appendMessage('user', text);
  isStreaming = true;

  // try SSE first
  try {
    const resp = await fetch(`/api/conversations/${currentConvoId}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ content: text }),
    });
    if (resp.ok && resp.headers.get('content-type')?.includes('text/event-stream')) {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let full = '';
      const bubble = appendStreamingBubble();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.chunk) {
                full += data.chunk;
                bubble.querySelector('#stream-text').textContent = full;
                scrollToBottom();
              }
              if (data.done) {
                bubble.remove();
                appendMessage('assistant', full);
              }
            } catch {}
          }
        }
      }
      isStreaming = false;
      return;
    }
  } catch (e) {
    console.warn('SSE failed, fallback to JSON', e);
  }

  // fallback JSON
  try {
    const msg = await post(`/api/conversations/${currentConvoId}/messages`, { content: text });
    appendMessage('assistant', msg.content);
  } catch (err) {
    appendMessage('assistant', '发送失败：' + err.message);
  }
  isStreaming = false;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function editDraft(btn) {
  const card = btn.closest('.draft-card');
  const div = card.querySelector('div');
  const text = div.textContent;
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style = 'width:100%;min-height:80px;';
  div.replaceWith(textarea);
  btn.textContent = '保存';
  btn.onclick = () => {
    const newText = textarea.value;
    const newDiv = document.createElement('div');
    newDiv.style = 'white-space:pre-wrap;';
    newDiv.textContent = newText;
    textarea.replaceWith(newDiv);
    btn.textContent = '编辑';
    btn.onclick = () => editDraft(btn);
  };
}

async function publishDraft(btn) {
  const card = btn.closest('.draft-card');
  const text = card.querySelector('div').textContent;
  if (!confirm('确定要将这篇草稿发布到社区吗？')) return;
  // For MVP, we create a simple draft record on the fly since drafts are not yet auto-saved
  // In a full implementation, drafts would have IDs from the backend.
  // Here we simply call the posts API directly as a fallback.
  try {
    await post('/api/posts', { content: text, tags: [] });
    alert('已发布到社区！');
    card.querySelector('.actions').innerHTML = '<span style="color:var(--primary);">已发布</span>';
  } catch (err) {
    alert('发布失败：' + err.message);
  }
}

init();
