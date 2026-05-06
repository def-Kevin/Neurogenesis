let currentConvoId = null;
let isStreaming = false;
let currentUserId = null;
let currentMode = 'ai';
const urlParams = new URLSearchParams(location.search);
const avatarId = urlParams.get('avatar_id');
const modeParam = urlParams.get('mode');
const convoIdParam = urlParams.get('convo_id');

async function init() {
  const user = await getMe();
  if (!user) return;
  currentUserId = user.id;

  if (avatarId) {
    document.querySelector('.chat-sidebar').style.display = 'none';
    document.getElementById('chat-header').textContent = '与分身聊天';
    const convos = await get('/api/conversations');
    const existing = (convos || []).find(c => c.avatar_id == avatarId);
    if (existing) {
      selectConvo(existing.id);
    } else {
      const convo = await post('/api/conversations', { avatar_id: parseInt(avatarId) });
      selectConvo(convo.id);
    }
  } else if (modeParam === 'direct') {
    currentMode = 'direct';
    document.getElementById('chat-header').textContent = '私信';
    // Hide new-conversation button in direct mode
    const newConvoBtn = document.querySelector('.chat-sidebar-header button');
    if (newConvoBtn) newConvoBtn.style.display = 'none';
    const mobileNewBtn = document.querySelector('.chat-mobile-nav button[onclick="createConversation()"]');
    if (mobileNewBtn) mobileNewBtn.style.display = 'none';
    await loadDirectConversations();
    if (convoIdParam) {
      selectDirectConvo(parseInt(convoIdParam));
    } else {
      const first = document.querySelector('.convo-item');
      if (first) {
        selectDirectConvo(parseInt(first.dataset.id));
      } else {
        currentConvoId = null;
        document.getElementById('chat-messages').innerHTML = '';
        document.getElementById('chat-messages').appendChild(
          renderEmptyState('还没有私信，去关注页发起对话吧', '', '')
        );
      }
    }
  } else {
    await loadConversations();
    const first = document.querySelector('.convo-item');
    if (first) {
      selectConvo(parseInt(first.dataset.id));
    } else {
      currentConvoId = null;
      document.getElementById('chat-messages').innerHTML = '';
      document.getElementById('chat-messages').appendChild(
        renderEmptyState('还没有对话，点击上方按钮开始', '新对话', 'javascript:createConversation()')
      );
    }
  }

  initTextarea();
  initSidebarAutoClose();

  // Adjust sidebar nav active state for direct mode
  if (currentMode === 'direct') {
    document.querySelectorAll('.chat-sidebar-nav a').forEach(a => a.classList.remove('active'));
    const dmLink = document.querySelector('.chat-sidebar-nav a[href*="mode=direct"]');
    if (dmLink) dmLink.classList.add('active');
  }
}

function initTextarea() {
  const ta = document.getElementById('msg-input');
  if (!ta) return;
  ta.addEventListener('input', () => {
    ta.rows = 1;
    const lineHeight = 24;
    const newRows = Math.min(5, Math.ceil(ta.scrollHeight / lineHeight));
    ta.rows = newRows;
  });
}

function handleInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (currentMode === 'direct') {
      sendDirectMessage();
    } else {
      sendMessage();
    }
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
    el.innerHTML = `
      <div class="title">${escapeHtml(c.title || '对话')}</div>
      <div class="preview">${escapeHtml(c.status || '')}</div>
      <div class="convo-actions">
        <button class="btn-small" style="padding:2px 6px;font-size:11px;" onclick="event.stopPropagation();renameConvo(${c.id}, this)">重命名</button>
        <button class="btn-small" style="padding:2px 6px;font-size:11px;color:#c33;" onclick="event.stopPropagation();deleteConvo(${c.id})">删除</button>
      </div>
    `;
    el.onclick = () => selectConvo(c.id);
    container.appendChild(el);
  });
}

async function loadDirectConversations() {
  const list = await get('/api/direct-messages/conversations');
  const container = document.getElementById('convo-list');
  container.innerHTML = '';
  (list || []).forEach(c => {
    const el = document.createElement('div');
    el.className = 'convo-item';
    el.dataset.id = c.id;
    const name = c.other_user?.nickname || c.other_user?.username || '未知用户';
    el.innerHTML = `
      <div class="title">${escapeHtml(name)}</div>
      <div class="preview">${escapeHtml(c.last_message_preview || '')}</div>
    `;
    el.onclick = () => selectDirectConvo(c.id);
    container.appendChild(el);
  });
}

async function selectDirectConvo(id) {
  currentConvoId = id;
  document.querySelectorAll('.convo-item').forEach(el => el.classList.toggle('active', parseInt(el.dataset.id) === id));
  const messages = await get(`/api/direct-messages/conversations/${id}/messages`);
  const container = document.getElementById('chat-messages');
  container.innerHTML = '';
  (messages || []).forEach(m => {
    const role = m.sender_id === currentUserId ? 'user' : 'assistant';
    appendMessage(role, m.content);
  });
  scrollToBottom();
}

async function sendDirectMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !currentConvoId) return;
  input.value = '';
  input.rows = 1;
  appendMessage('user', text);
  try {
    await post(`/api/direct-messages/conversations/${currentConvoId}/messages`, { content: text });
  } catch (err) {
    appendMessage('assistant', '发送失败：' + err.message);
  }
}

async function renameConvo(id, btn) {
  const item = btn.closest('.convo-item');
  const titleEl = item.querySelector('.title');
  const current = titleEl.textContent;
  const input = document.createElement('input');
  input.value = current;
  input.className = 'text-sm';
  input.style.cssText = 'width:100%;padding:2px 6px;border:1px solid var(--primary);border-radius:4px;font-family:inherit;';
  titleEl.replaceWith(input);
  input.focus();

  const save = async () => {
    const newTitle = input.value.trim();
    if (newTitle && newTitle !== current) {
      try {
        await fetch(`/api/conversations/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ title: newTitle }),
        });
        await loadConversations();
        document.querySelector(`.convo-item[data-id="${id}"]`)?.classList.add('active');
      } catch (err) {
        showToast('重命名失败', 'error');
      }
    } else {
      await loadConversations();
      document.querySelector(`.convo-item[data-id="${id}"]`)?.classList.add('active');
    }
  };

  input.onblur = save;
  input.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); input.blur(); } };
}

async function deleteConvo(id) {
  showConfirm('确定删除这个对话吗？', async () => {
    try {
      await del(`/api/conversations/${id}`);
      await loadConversations();
      const first = document.querySelector('.convo-item');
      if (first) selectConvo(parseInt(first.dataset.id));
      else {
        currentConvoId = null;
        document.getElementById('chat-messages').innerHTML = '';
        document.getElementById('chat-header').textContent = '选择一个对话开始';
        document.getElementById('chat-messages').appendChild(
          renderEmptyState('还没有对话，点击上方按钮开始', '新对话', 'javascript:createConversation()')
        );
      }
    } catch (err) {
      showToast('删除失败', 'error');
    }
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
  (messages || []).forEach(m => appendMessage(m.role, m.content, m.tool_calls));
  scrollToBottom();
}

function appendMessage(role, content, toolCalls) {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  let html = escapeHtml(content);

  // draft cards
  html = html.replace(/\[DRAFT\]([\s\S]*?)\[\/DRAFT\]/g, (_, draft) => {
    return `<div class="draft-card"><div style="white-space:pre-wrap;">${escapeHtml(draft.trim())}</div><div class="actions"><button class="btn-small" onclick="editDraft(this)">编辑</button><button class="btn-small primary" onclick="publishDraft(this)">发布</button></div></div>`;
  });

  // rec cards
  html = html.replace(/\[REC\]([^|]+)\|([^|]+)\|([^|]+)\|([\s\S]*?)\[\/REC\]/g, (_, type, title, creator, reason) => {
    return `<div class="rec-card" data-rec-type="${escapeHtml(type.trim())}" data-rec-title="${escapeHtml(title.trim())}" data-rec-creator="${escapeHtml(creator.trim())}" data-rec-reason="${escapeHtml(reason.trim())}"><div style="font-weight:600;">${escapeHtml(title)} · ${escapeHtml(creator)}</div><div style="font-size:12px;color:var(--text-secondary);">${escapeHtml(type)}</div><div style="margin-top:4px;">${escapeHtml(reason.trim())}</div><div class="actions"><button class="btn-small" onclick="recFeedback(this, '想看')">想看</button><button class="btn-small" onclick="recFeedback(this, '不感兴趣')">不感兴趣</button></div></div>`;
  });

  let toolBadge = '';
  if (toolCalls) {
    try {
      const calls = JSON.parse(toolCalls);
      if (Array.isArray(calls) && calls.length > 0) {
        const names = calls.map(c => c.function?.name || 'tool').join(', ');
        toolBadge = `<span style="display:inline-block;background:var(--primary-light);color:var(--primary);padding:2px 8px;border-radius:12px;font-size:11px;margin-bottom:6px;">使用了工具: ${escapeHtml(names)}</span>`;
      }
    } catch (e) {}
  }

  let actionsHtml = '';
  if (role === 'assistant') {
    actionsHtml = `
      <div class="msg-actions">
        <button class="btn-small" style="padding:2px 8px;font-size:11px;color:var(--text-tertiary);border:none;background:transparent;" onclick="copyToClipboard(this.closest('.message-row').querySelector('.bubble').textContent)">复制</button>
        <button class="btn-small" style="padding:2px 8px;font-size:11px;color:var(--text-tertiary);border:none;background:transparent;" onclick="regenerateMessage(this)">重新生成</button>
      </div>
    `;
  }

  row.innerHTML = `${toolBadge}<div class="bubble ${role}">${html}</div>${actionsHtml}`;
  container.appendChild(row);
  scrollToBottom();
}

function appendStreamingBubble() {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = 'streaming-msg';
  row.innerHTML = '<div class="bubble assistant"><span id="stream-text"></span><span style="animation:pulse 1s infinite;">...</span></div>';
  container.appendChild(row);
  scrollToBottom();
  return row;
}

function scrollToBottom() {
  const container = document.getElementById('chat-messages');
  container.scrollTop = container.scrollHeight;
}

async function streamResponse(convoId, text) {
  const sendBtn = document.getElementById('send-btn');
  const sendBtnIcon = document.getElementById('send-btn-icon');
  const input = document.getElementById('msg-input');
  sendBtn.disabled = true;
  sendBtn.style.opacity = '0.7';
  if (sendBtnIcon) sendBtnIcon.className = 'ph ph-spinner ph-spin';
  input.disabled = true;
  isStreaming = true;

  // try SSE first
  try {
    const resp = await fetch(`/api/conversations/${convoId}/messages/stream`, {
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
                const st = bubble.querySelector('#stream-text');
                if (st) st.textContent = full;
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
      sendBtn.disabled = false;
      sendBtn.style.opacity = '1';
      if (sendBtnIcon) sendBtnIcon.className = 'ph ph-paper-plane-right';
      input.disabled = false;
      input.focus();
      return;
    }
  } catch (e) {
    console.warn('SSE failed, fallback to JSON', e);
  }

  // fallback JSON
  try {
    const msg = await post(`/api/conversations/${convoId}/messages`, { content: text });
    appendMessage('assistant', msg.content);
  } catch (err) {
    appendMessage('assistant', '发送失败：' + err.message);
  }

  isStreaming = false;
  sendBtn.disabled = false;
  sendBtn.style.opacity = '1';
  if (sendBtnIcon) sendBtnIcon.className = 'ph ph-paper-plane-right';
  input.disabled = false;
  input.focus();
}

async function sendMessage() {
  if (currentMode === 'direct') {
    sendDirectMessage();
    return;
  }
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !currentConvoId || isStreaming) return;
  input.value = '';
  input.rows = 1;
  appendMessage('user', text);
  await streamResponse(currentConvoId, text);
}

async function regenerateMessage(btn) {
  if (!currentConvoId || isStreaming) return;
  const row = btn.closest('.message-row');
  const userRow = row.previousElementSibling;
  if (!userRow || !userRow.classList.contains('user')) return;
  const text = userRow.querySelector('.bubble').textContent;
  row.remove();
  await streamResponse(currentConvoId, text);
}

async function ensureDraftSaved(card) {
  let draftId = card.dataset.draftId;
  if (!draftId) {
    const text = card.querySelector('div').textContent;
    const res = await post(`/api/conversations/${currentConvoId}/drafts`, { draft_content: text });
    draftId = res.id;
    card.dataset.draftId = draftId;
  }
  return draftId;
}

function editDraft(btn) {
  const card = btn.closest('.draft-card');
  const div = card.querySelector('div');
  const text = div.textContent;
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style = 'width:100%;min-height:80px;font-family:inherit;';
  div.replaceWith(textarea);
  btn.textContent = '保存';
  btn.onclick = async () => {
    const newText = textarea.value;
    const newDiv = document.createElement('div');
    newDiv.style = 'white-space:pre-wrap;';
    newDiv.textContent = newText;
    textarea.replaceWith(newDiv);
    btn.textContent = '编辑';
    btn.onclick = () => editDraft(btn);
    try {
      const draftId = await ensureDraftSaved(card);
      await put(`/api/conversations/${currentConvoId}/drafts/${draftId}`, { draft_content: newText });
      showToast('草稿已保存', 'success');
    } catch (err) {
      showToast('保存失败：' + err.message, 'error');
    }
  };
}

async function publishDraft(btn) {
  const card = btn.closest('.draft-card');
  const text = card.querySelector('div').textContent;
  if (!confirm('确定要将这篇草稿发布到社区吗？')) return;
  try {
    const draftId = await ensureDraftSaved(card);
    await post(`/api/conversations/${currentConvoId}/publish?draft_id=${draftId}`);
    showToast('已发布到社区！', 'success');
    card.querySelector('.actions').innerHTML = '<span style="color:var(--primary);">已发布</span>';
  } catch (err) {
    showToast('发布失败：' + err.message, 'error');
  }
}

async function recFeedback(btn, feedback) {
  const card = btn.closest('.rec-card');
  let recId = card.dataset.recId;
  if (!recId) {
    try {
      const res = await post(`/api/conversations/${currentConvoId}/recommendations`, {
        work_type: card.dataset.recType,
        work_title: card.dataset.recTitle,
        work_creator: card.dataset.recCreator,
        reason: card.dataset.recReason,
      });
      recId = res.id;
      card.dataset.recId = recId;
    } catch (err) {
      showToast('记录失败：' + err.message, 'error');
      return;
    }
  }
  try {
    await post(`/api/recommendations/${recId}/feedback?feedback=${encodeURIComponent(feedback)}`);
    showToast('反馈已记录', 'success');
    card.querySelector('.actions').innerHTML = `<span style="color:var(--primary);">已${feedback}</span>`;
  } catch (err) {
    showToast('反馈失败：' + err.message, 'error');
  }
}

function toggleMobileSidebar() {
  const sidebar = document.querySelector('.chat-sidebar');
  let overlay = document.querySelector('.chat-sidebar-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'chat-sidebar-overlay';
    overlay.onclick = toggleMobileSidebar;
    document.querySelector('.chat-layout').appendChild(overlay);
  }
  const isOpen = sidebar.classList.toggle('open');
  overlay.classList.toggle('open', isOpen);
}

// Auto-close sidebar when clicking nav links on mobile
function initSidebarAutoClose() {
  const sidebar = document.querySelector('.chat-sidebar');
  if (!sidebar) return;
  sidebar.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 640) {
        sidebar.classList.remove('open');
        const overlay = document.querySelector('.chat-sidebar-overlay');
        if (overlay) overlay.classList.remove('open');
      }
    });
  });
}

init();
