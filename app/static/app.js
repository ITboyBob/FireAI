const workspace = document.querySelector(".workspace");
const apiBase = workspace?.dataset.conversationEndpoint || "/api/conversations";

const elements = {
  conversationList: document.getElementById("conversation-list"),
  conversationCount: document.getElementById("conversation-count"),
  conversationTitle: document.getElementById("conversation-title"),
  conversationSubtitle: document.getElementById("conversation-subtitle"),
  conversationThread: document.getElementById("conversation-thread"),
  newConversationButton: document.getElementById("new-conversation-button"),
  renameConversationButton: document.getElementById("rename-conversation-button"),
  deleteConversationButton: document.getElementById("delete-conversation-button"),
  composerForm: document.getElementById("composer-form"),
  composerInput: document.getElementById("composer-input"),
  sendButton: document.getElementById("send-button"),
  requestStatus: document.getElementById("request-status"),
  errorPanel: document.getElementById("error-panel"),
};

const state = {
  conversations: [],
  activeConversationId: null,
  activeDetail: null,
  loading: false,
};

function setStatus(text) {
  if (elements.requestStatus) {
    elements.requestStatus.textContent = text;
  }
}

function showError(message) {
  if (!elements.errorPanel) {
    return;
  }
  elements.errorPanel.hidden = false;
  elements.errorPanel.textContent = message;
}

function hideError() {
  if (!elements.errorPanel) {
    return;
  }
  elements.errorPanel.hidden = true;
  elements.errorPanel.textContent = "";
}

function setLoading(isLoading) {
  state.loading = isLoading;
  if (elements.sendButton) {
    elements.sendButton.disabled = isLoading;
    elements.sendButton.textContent = isLoading ? "发送中..." : "发送问题";
  }
  if (elements.newConversationButton) {
    elements.newConversationButton.disabled = isLoading;
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败，状态码 ${response.status}`);
  }
  return payload;
}

function renderConversationList() {
  if (!elements.conversationList || !elements.conversationCount) {
    return;
  }

  elements.conversationCount.textContent = String(state.conversations.length);
  elements.conversationList.replaceChildren();

  if (state.conversations.length === 0) {
    const empty = document.createElement("li");
    empty.className = "conversation-list-empty";
    empty.textContent = "暂时还没有会话。";
    elements.conversationList.appendChild(empty);
    return;
  }

  for (const conversation of state.conversations) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const title = document.createElement("span");
    const meta = document.createElement("small");

    item.className = "conversation-item";
    button.type = "button";
    button.className = "conversation-button";
    if (conversation.id === state.activeConversationId) {
      button.classList.add("is-active");
    }

    title.className = "conversation-button-title";
    title.textContent = conversation.title || "未命名会话";

    meta.className = "conversation-button-meta";
    meta.textContent = conversation.last_message_at
      ? `最近更新 ${conversation.last_message_at.slice(0, 16).replace("T", " ")}`
      : "尚无消息";

    button.append(title, meta);
    button.addEventListener("click", () => void loadConversationDetail(conversation.id));
    item.appendChild(button);
    elements.conversationList.appendChild(item);
  }
}

function renderThread() {
  if (!elements.conversationThread || !elements.conversationTitle || !elements.conversationSubtitle) {
    return;
  }

  const detail = state.activeDetail;
  elements.conversationThread.replaceChildren();

  if (!detail) {
    elements.conversationTitle.textContent = "请选择会话";
    elements.conversationSubtitle.textContent = "会话详情、法律依据和修正提示会显示在这里。";
    elements.conversationThread.appendChild(buildThreadEmptyState());
    return;
  }

  elements.conversationTitle.textContent = detail.conversation.title || "未命名会话";
  elements.conversationSubtitle.textContent =
    detail.messages.length > 0
      ? `共 ${detail.messages.length} 条消息，继续追问时系统仍会重新检索。`
      : "当前会话还没有消息，直接在下方输入即可。";

  if (detail.history_summary) {
    const summary = document.createElement("article");
    summary.className = "history-summary";
    summary.innerHTML = `
      <p class="history-summary-label">更早历史摘要</p>
      <p class="history-summary-text"></p>
    `;
    summary.querySelector(".history-summary-text").textContent = detail.history_summary;
    elements.conversationThread.appendChild(summary);
  }

  if (!detail.messages.length) {
    elements.conversationThread.appendChild(buildThreadEmptyState("当前会话还没有消息。"));
    return;
  }

  for (const message of detail.messages) {
    elements.conversationThread.appendChild(buildMessageCard(message));
  }
  elements.conversationThread.scrollTop = elements.conversationThread.scrollHeight;
}

function buildThreadEmptyState(message = "还没有打开任何会话。") {
  const empty = document.createElement("div");
  empty.className = "thread-empty";
  empty.innerHTML = `
    <p class="empty-title"></p>
    <p>可以先新建会话，也可以直接使用下方输入框发起提问。</p>
  `;
  empty.querySelector(".empty-title").textContent = message;
  return empty;
}

function buildMessageCard(message) {
  const card = document.createElement("article");
  card.className = `message-card message-card--${message.role}`;

  const header = document.createElement("div");
  header.className = "message-header";
  header.innerHTML = `
    <span class="message-role">${message.role === "user" ? "你" : "助手"}</span>
    <span class="message-time">${message.created_at ? message.created_at.slice(0, 16).replace("T", " ") : ""}</span>
  `;

  const body = document.createElement("p");
  body.className = "message-body";
  body.textContent = message.content;
  card.append(header, body);

  if (message.role === "assistant") {
    if (message.correction_notice) {
      const correction = document.createElement("p");
      correction.className = "message-correction";
      correction.textContent = message.correction_notice;
      card.appendChild(correction);
    }

    if (message.legal_basis?.length) {
      const basis = document.createElement("ul");
      basis.className = "basis-list";
      for (const item of message.legal_basis) {
        const row = document.createElement("li");
        row.textContent = item;
        basis.appendChild(row);
      }
      card.appendChild(basis);
    }

    if (message.clause_texts?.length) {
      const evidence = document.createElement("div");
      evidence.className = "clause-stack";
      for (const item of message.clause_texts) {
        const block = document.createElement("article");
        const path = document.createElement("p");
        const text = document.createElement("p");
        block.className = "clause-block";
        path.className = "clause-path";
        path.textContent = item.path;
        text.className = "clause-text";
        text.textContent = item.text;
        block.append(path, text);
        evidence.appendChild(block);
      }
      card.appendChild(evidence);
    }
  }

  return card;
}

async function loadConversationList(preferredConversationId = state.activeConversationId) {
  state.conversations = await requestJson(apiBase);
  if (!state.conversations.some((item) => item.id === preferredConversationId)) {
    state.activeConversationId = state.conversations[0]?.id || null;
  } else {
    state.activeConversationId = preferredConversationId;
  }
  renderConversationList();
}

async function loadConversationDetail(conversationId) {
  hideError();
  state.activeConversationId = conversationId;
  renderConversationList();
  state.activeDetail = await requestJson(`${apiBase}/${conversationId}`);
  renderThread();
}

async function createConversation() {
  const created = await requestJson(apiBase, {
    method: "POST",
    body: JSON.stringify({}),
  });
  await loadConversationList(created.id);
  await loadConversationDetail(created.id);
  return created.id;
}

async function renameConversation() {
  if (!state.activeConversationId || !state.activeDetail) {
    showError("请先选择要重命名的会话。");
    return;
  }

  const title = window.prompt("输入新的会话标题", state.activeDetail.conversation.title || "新会话");
  if (!title) {
    return;
  }

  hideError();
  await requestJson(`${apiBase}/${state.activeConversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  await loadConversationList(state.activeConversationId);
  await loadConversationDetail(state.activeConversationId);
  setStatus("会话标题已更新。");
}

async function deleteConversation() {
  if (!state.activeConversationId || !state.activeDetail) {
    showError("请先选择要删除的会话。");
    return;
  }

  const confirmed = window.confirm(`确认删除“${state.activeDetail.conversation.title}”吗？`);
  if (!confirmed) {
    return;
  }

  hideError();
  await requestJson(`${apiBase}/${state.activeConversationId}`, { method: "DELETE" });
  state.activeDetail = null;
  state.activeConversationId = null;
  await loadConversationList();
  if (state.activeConversationId) {
    await loadConversationDetail(state.activeConversationId);
  } else {
    renderThread();
  }
  setStatus("会话已删除。");
}

async function sendMessage(message) {
  hideError();
  setLoading(true);

  try {
    let conversationId = state.activeConversationId;
    if (!conversationId) {
      conversationId = await createConversation();
    }

    await requestJson(`${apiBase}/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });

    if (elements.composerInput) {
      elements.composerInput.value = "";
    }
    await loadConversationList(conversationId);
    await loadConversationDetail(conversationId);
    setStatus("已收到新的会话回答。");
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "请求失败。";
    showError(messageText);
    setStatus("请求失败。");
  } finally {
    setLoading(false);
  }
}

elements.newConversationButton?.addEventListener("click", () => {
  void createConversation().catch((error) => {
    showError(error instanceof Error ? error.message : "创建会话失败。");
  });
});

elements.renameConversationButton?.addEventListener("click", () => {
  void renameConversation().catch((error) => {
    showError(error instanceof Error ? error.message : "重命名会话失败。");
  });
});

elements.deleteConversationButton?.addEventListener("click", () => {
  void deleteConversation().catch((error) => {
    showError(error instanceof Error ? error.message : "删除会话失败。");
  });
});

elements.composerForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = elements.composerInput?.value.trim() || "";
  if (!message) {
    showError("请输入问题后再发送。");
    return;
  }
  void sendMessage(message);
});

for (const trigger of document.querySelectorAll("[data-prompt]")) {
  trigger.addEventListener("click", () => {
    const prompt = trigger.getAttribute("data-prompt") || "";
    if (elements.composerInput) {
      elements.composerInput.value = prompt;
      elements.composerInput.focus();
    }
  });
}

async function bootstrap() {
  setStatus("正在加载历史会话。");
  try {
    await loadConversationList();
    if (state.activeConversationId) {
      await loadConversationDetail(state.activeConversationId);
      setStatus("已恢复最近一次会话。");
    } else {
      renderThread();
      setStatus("暂无历史会话，可直接新建。");
    }
  } catch (error) {
    showError(error instanceof Error ? error.message : "初始化失败。");
    setStatus("初始化失败。");
  }
}

void bootstrap();
