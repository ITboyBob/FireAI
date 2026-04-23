const workspace = document.querySelector(".workspace");
const apiBase = workspace?.dataset.conversationEndpoint || "/api/conversations";
const initialConversationId = workspace?.dataset.initialConversationId || "";

const elements = {
  errorPanel: document.getElementById("error-panel"),
  pageHeading: document.getElementById("page-heading"),
  conversationList: document.getElementById("conversation-list"),
  conversationCount: document.getElementById("conversation-count"),
  newConversationButton: document.getElementById("new-conversation-button"),
  homeView: document.getElementById("home-view"),
  threadView: document.getElementById("thread-view"),
  conversationTitle: document.getElementById("conversation-title"),
  conversationSubtitle: document.getElementById("conversation-subtitle"),
  conversationThread: document.getElementById("conversation-thread"),
  homeComposerForm: document.getElementById("home-composer-form"),
  homeComposerInput: document.getElementById("home-composer-input"),
  homeSendButton: document.getElementById("home-send-button"),
  homeRequestStatus: document.getElementById("home-request-status"),
  threadComposerForm: document.getElementById("thread-composer-form"),
  threadComposerInput: document.getElementById("thread-composer-input"),
  threadSendButton: document.getElementById("thread-send-button"),
  threadRequestStatus: document.getElementById("thread-request-status"),
};

const state = {
  conversations: [],
  activeConversationId: initialConversationId || null,
  activeDetail: null,
  loading: false,
  threadLoading: false,
  view: initialConversationId ? "thread" : "home",
};

function setView(view) {
  state.view = view;
  document.body.dataset.view = view;
  if (elements.homeView) {
    elements.homeView.hidden = view !== "home";
  }
  if (elements.threadView) {
    elements.threadView.hidden = view !== "thread";
  }
  if (elements.pageHeading) {
    elements.pageHeading.textContent =
      view === "home" ? "消防问答指挥台" : "消防法规对话窗口";
  }
}

function setStatus(text) {
  if (elements.homeRequestStatus) {
    elements.homeRequestStatus.textContent = text;
  }
  if (elements.threadRequestStatus) {
    elements.threadRequestStatus.textContent = text;
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
  for (const button of [
    elements.homeSendButton,
    elements.threadSendButton,
    elements.newConversationButton,
  ]) {
    if (button) {
      button.disabled = isLoading;
    }
  }
}

function getRouteConversationId(pathname = window.location.pathname) {
  const matched = pathname.match(/^\/conversations\/([^/]+)$/);
  return matched ? decodeURIComponent(matched[1]) : null;
}

function updateUrl(conversationId, { replace = false } = {}) {
  const url = conversationId ? `/conversations/${encodeURIComponent(conversationId)}` : "/";
  const method = replace ? "replaceState" : "pushState";
  window.history[method]({ conversationId }, "", url);
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }
  try {
    const date = new Date(value);
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  } catch {
    return value.slice(5, 16).replace("T", " ");
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

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : { detail: await response.text() };

  if (!response.ok) {
    throw new Error(payload.detail || `请求失败，状态码 ${response.status}`);
  }
  return payload;
}

function buildConversationPlaceholder(conversationId) {
  const summary = state.conversations.find((item) => item.id === conversationId);
  return {
    conversation:
      summary || {
        id: conversationId,
        title: "新会话",
        auto_title: true,
        updated_at: new Date().toISOString(),
        last_message_at: null,
      },
    messages: [],
    history_summary: "",
  };
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
    empty.textContent = "还没有历史会话，可以直接从首页发起第一轮提问。";
    elements.conversationList.appendChild(empty);
    return;
  }

  for (const conversation of state.conversations) {
    const row = document.createElement("li");
    row.className = "sidebar-row";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "sidebar-item";
    button.setAttribute("data-testid", "conversation-list-item");
    if (conversation.id === state.activeConversationId) {
      button.classList.add("is-active");
    }

    const title = document.createElement("span");
    title.className = "sidebar-item-title";
    title.textContent = conversation.title || "未命名会话";

    const meta = document.createElement("small");
    meta.className = "sidebar-item-meta";
    meta.textContent = conversation.last_message_at
      ? `最近更新 ${formatDateTime(conversation.last_message_at)}`
      : "尚无消息";

    button.append(title, meta);
    button.addEventListener("click", () => {
      void openConversation(conversation.id);
    });

    const actions = document.createElement("div");
    actions.className = "sidebar-row-actions";

    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.className = "sidebar-action";
    renameButton.textContent = "改";
    renameButton.title = "重命名";
    renameButton.addEventListener("click", (event) => {
      event.stopPropagation();
      void renameConversation(conversation.id);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "sidebar-action";
    deleteButton.textContent = "删";
    deleteButton.title = "删除";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      void deleteConversation(conversation.id);
    });

    actions.append(renameButton, deleteButton);
    row.append(button, actions);
    elements.conversationList.appendChild(row);
  }
}

function buildThreadState(title, copy) {
  const panel = document.createElement("article");
  panel.className = "thread-state";
  panel.innerHTML = `
    <h3 class="thread-state-title"></h3>
    <p class="thread-state-copy"></p>
  `;
  panel.querySelector(".thread-state-title").textContent = title;
  panel.querySelector(".thread-state-copy").textContent = copy;
  return panel;
}

function buildPendingAssistant(createdAt) {
  return {
    id: `pending-${Date.now()}`,
    role: "assistant",
    content: "",
    created_at: createdAt,
    legal_basis: [],
    clause_texts: [],
    correction_notice: "",
    isPending: true,
  };
}

function buildUserDraftMessage(message) {
  return {
    id: `local-user-${Date.now()}`,
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
    legal_basis: [],
    clause_texts: [],
    correction_notice: "",
  };
}

function renderThread() {
  if (!elements.conversationThread || !elements.conversationTitle || !elements.conversationSubtitle) {
    return;
  }

  const detail = state.activeDetail;
  elements.conversationThread.replaceChildren();

  if (!detail) {
    elements.conversationTitle.textContent = "请选择会话";
    elements.conversationSubtitle.textContent = "打开历史会话或从首页发送第一条问题。";
    elements.conversationThread.appendChild(
      buildThreadState("还没有打开会话", "当前页用于展示会话消息、修正提示、法律依据和证据区。")
    );
    return;
  }

  const title = detail.conversation?.title || "未命名会话";
  elements.conversationTitle.textContent = title;
  elements.conversationSubtitle.textContent = state.threadLoading
    ? "正在加载会话详情。"
    : detail.messages.length > 0
      ? `当前共 ${detail.messages.length} 条消息，继续追问时系统会重新检索最新证据。`
      : "当前会话还没有消息，直接在下方输入即可。";

  if (detail.history_summary) {
    elements.conversationThread.appendChild(
      buildThreadState("更早历史摘要", detail.history_summary)
    );
  }

  if (state.threadLoading) {
    elements.conversationThread.appendChild(
      buildThreadState("正在读取历史会话", "会话消息、证据区和修正提示正在恢复。")
    );
    return;
  }

  if (!detail.messages.length) {
    elements.conversationThread.appendChild(
      buildThreadState("当前会话为空", "在下方输入问题后，系统会立即写入用户消息并显示处理中状态。")
    );
    return;
  }

  for (const message of detail.messages) {
    elements.conversationThread.appendChild(buildMessageCard(message));
  }

  elements.conversationThread.scrollTop = elements.conversationThread.scrollHeight;
}

function buildMessageCard(message) {
  const row = document.createElement("article");
  row.className = `message-row message-row--${message.role}`;

  if (message.role === "user") {
    const bubble = document.createElement("div");
    bubble.className = "user-bubble";
    bubble.innerHTML = `
      <p class="user-copy"></p>
      <small class="bubble-meta"></small>
    `;
    bubble.querySelector(".user-copy").textContent = message.content;
    bubble.querySelector(".bubble-meta").textContent = formatDateTime(message.created_at) || "刚刚";
    row.appendChild(bubble);
    return row;
  }

  const panel = document.createElement("div");
  panel.className = "assistant-panel";

  const rail = document.createElement("div");
  rail.className = "assistant-rail";

  if (message.correction_notice) {
    const hint = document.createElement("div");
    hint.className = "assistant-hint";
    hint.innerHTML = `
      <span class="assistant-eyebrow">Correction Hint</span>
      <span class="assistant-hint-copy"></span>
    `;
    hint.querySelector(".assistant-hint-copy").textContent = message.correction_notice;
    rail.appendChild(hint);
  }

  const title = document.createElement("h3");
  title.className = "assistant-title";
  title.textContent = message.isPending ? "正在检索与生成回答" : "回答";
  rail.appendChild(title);

  if (message.isPending) {
    const pending = document.createElement("div");
    pending.className = "assistant-pending";
    pending.innerHTML = `
      <div class="pending-line"></div>
      <div class="pending-line pending-line--mid"></div>
      <div class="pending-line pending-line--short"></div>
      <div class="pending-card"></div>
    `;
    rail.appendChild(pending);
  } else {
    const copy = document.createElement("p");
    copy.className = "assistant-copy";
    copy.setAttribute("data-testid", "assistant-copy");
    copy.textContent = message.content;
    rail.appendChild(copy);
  }

  if (message.isError) {
    const error = document.createElement("div");
    error.className = "assistant-error";
    error.textContent = message.errorText || "本轮发送失败。";
    rail.appendChild(error);
  }

  if (!message.isPending && message.legal_basis?.length) {
    const basis = document.createElement("ul");
    basis.className = "basis-list";
    basis.setAttribute("data-testid", "basis-list");
    for (const item of message.legal_basis) {
      const rowItem = document.createElement("li");
      rowItem.textContent = item;
      basis.appendChild(rowItem);
    }
    rail.appendChild(basis);
  }

  if (!message.isPending && message.clause_texts?.length) {
    const evidence = document.createElement("section");
    evidence.className = "evidence-panel";
    evidence.innerHTML = `
      <div class="evidence-head">
        <h4 class="evidence-title">证据区</h4>
        <span class="evidence-tag">SOURCE VERIFIED</span>
      </div>
      <div class="evidence-grid"></div>
    `;
    const grid = evidence.querySelector(".evidence-grid");
    for (const item of message.clause_texts) {
      const card = document.createElement("article");
      card.className = "evidence-card";
      card.setAttribute("data-testid", "evidence-card");
      card.innerHTML = `
        <p class="evidence-path" data-testid="evidence-path"></p>
        <p class="evidence-copy" data-testid="evidence-copy"></p>
      `;
      card.querySelector(".evidence-path").textContent = item.path;
      card.querySelector(".evidence-copy").textContent = item.text;
      grid.appendChild(card);
    }
    rail.appendChild(evidence);
  }

  const meta = document.createElement("small");
  meta.className = "bubble-meta";
  meta.textContent = formatDateTime(message.created_at) || "刚刚";
  rail.appendChild(meta);

  panel.appendChild(rail);
  row.appendChild(panel);
  return row;
}

async function loadConversationList() {
  state.conversations = await requestJson(apiBase);
  if (state.activeConversationId && !state.conversations.some((item) => item.id === state.activeConversationId)) {
    state.activeConversationId = null;
    state.activeDetail = null;
  }
  renderConversationList();
}

async function loadConversationDetail(conversationId) {
  state.threadLoading = true;
  state.activeConversationId = conversationId;
  state.activeDetail = buildConversationPlaceholder(conversationId);
  setView("thread");
  renderConversationList();
  renderThread();

  try {
    state.activeDetail = await requestJson(`${apiBase}/${conversationId}`);
    state.threadLoading = false;
    renderConversationList();
    renderThread();
  } catch (error) {
    state.threadLoading = false;
    throw error;
  }
}

async function openConversation(conversationId, { push = true } = {}) {
  hideError();
  if (push) {
    updateUrl(conversationId);
  }
  try {
    await loadConversationDetail(conversationId);
    setStatus("已恢复历史会话。");
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "读取会话失败。";
    showError(messageText);
    state.activeConversationId = null;
    state.activeDetail = null;
    setView("home");
    updateUrl(null, { replace: true });
    renderConversationList();
    renderThread();
    setStatus("会话读取失败，已返回首页。");
  }
}

async function createConversation({ push = true } = {}) {
  const created = await requestJson(apiBase, {
    method: "POST",
    body: JSON.stringify({}),
  });
  state.activeConversationId = created.id;
  state.activeDetail = {
    conversation: created,
    messages: [],
    history_summary: "",
  };
  setView("thread");
  if (push) {
    updateUrl(created.id);
  }
  await loadConversationList();
  renderThread();
  return created.id;
}

async function renameConversation(conversationId = state.activeConversationId) {
  if (!conversationId) {
    showError("请先选择要重命名的会话。");
    return;
  }

  const currentTitle =
    state.activeDetail?.conversation?.id === conversationId
      ? state.activeDetail.conversation.title
      : state.conversations.find((item) => item.id === conversationId)?.title || "新会话";
  const title = window.prompt("输入新的会话标题", currentTitle || "新会话");
  if (!title) {
    return;
  }

  hideError();
  await requestJson(`${apiBase}/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  await loadConversationList();
  if (state.activeConversationId === conversationId) {
    await openConversation(conversationId, { push: false });
  }
  setStatus("会话标题已更新。");
}

async function deleteConversation(conversationId = state.activeConversationId) {
  if (!conversationId) {
    showError("请先选择要删除的会话。");
    return;
  }

  const currentTitle =
    state.activeDetail?.conversation?.id === conversationId
      ? state.activeDetail.conversation.title
      : state.conversations.find((item) => item.id === conversationId)?.title || "当前会话";
  if (!window.confirm(`确认删除“${currentTitle}”吗？`)) {
    return;
  }

  hideError();
  await requestJson(`${apiBase}/${conversationId}`, { method: "DELETE" });
  const wasActive = state.activeConversationId === conversationId;
  if (wasActive) {
    state.activeConversationId = null;
    state.activeDetail = null;
    setView("home");
    updateUrl(null);
    renderThread();
  }
  await loadConversationList();
  setStatus("会话已删除。");
}

function updateComposerValues(value) {
  if (elements.homeComposerInput) {
    elements.homeComposerInput.value = value;
  }
  if (elements.threadComposerInput) {
    elements.threadComposerInput.value = value;
  }
}

function clearComposerValues() {
  updateComposerValues("");
}

function goHome() {
  state.activeConversationId = null;
  state.activeDetail = null;
  setView("home");
  updateUrl(null);
  renderConversationList();
  renderThread();
  clearComposerValues();
  setStatus("首页已就绪，可以直接提问。");
}

function replacePendingAssistantWithError(messageText) {
  if (!state.activeDetail) {
    return;
  }
  const messages = [...state.activeDetail.messages];
  const lastIndex = messages.findLastIndex((item) => item.isPending);
  if (lastIndex === -1) {
    return;
  }
  messages[lastIndex] = {
    id: `error-${Date.now()}`,
    role: "assistant",
    content: "本轮发送失败。",
    created_at: new Date().toISOString(),
    legal_basis: [],
    clause_texts: [],
    correction_notice: "",
    isError: true,
    errorText: messageText,
  };
  state.activeDetail = { ...state.activeDetail, messages };
  renderThread();
}

async function sendMessage(message, source) {
  hideError();
  setLoading(true);
  updateComposerValues(message);

  try {
    let conversationId = state.activeConversationId;
    if (!conversationId) {
      conversationId = await createConversation();
    }

    if (!state.activeDetail || state.activeDetail.conversation.id !== conversationId) {
      state.activeDetail = buildConversationPlaceholder(conversationId);
    }

    const draftMessages = [...state.activeDetail.messages, buildUserDraftMessage(message)];
    draftMessages.push(buildPendingAssistant(new Date().toISOString()));
    state.activeDetail = {
      ...state.activeDetail,
      messages: draftMessages,
    };
    setView("thread");
    renderConversationList();
    renderThread();
    setStatus("正在检索最新证据并生成回答。");

    await fetchStreamMessage(conversationId, message, source);
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "请求失败。";
    showError(messageText);
    replacePendingAssistantWithError(messageText);
    setStatus("请求失败，请检查错误信息后重试。可能已生成新的用户消息，重试将产生新的提问。");
  } finally {
    setLoading(false);
  }
}

async function fetchStreamMessage(conversationId, message, source) {
  const response = await fetch(`${apiBase}/${conversationId}/messages/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/x-ndjson"
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    let detail = `状态码 ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (e) {}
    throw new Error(`请求失败，${detail}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let assistantData = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let newlineIndex;
    while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line) {
        assistantData = handleStreamEvent(JSON.parse(line)) || assistantData;
      }
    }
  }

  if (buffer.trim()) {
    assistantData = handleStreamEvent(JSON.parse(buffer.trim())) || assistantData;
  }

  if (!assistantData) {
    throw new Error("未能获取完整回答");
  }

  const cards = elements.conversationThread.querySelectorAll(".message-row--assistant");
  const lastCard = cards[cards.length - 1];
  
  if (lastCard) {
    setStatus("正在逐字显示回答...");
    await typewriteMessage(lastCard, assistantData);
  }

  clearComposerValues();
  await loadConversationList();
  // refresh detail behind the scenes
  const rawDetail = await requestJson(`${apiBase}/${conversationId}`);
  state.activeDetail = rawDetail;
  // intentionally do NOT re-renderThread here so we don't flash the UI, it's already rendered
  setStatus(source === "home" ? "已进入会话并收到回答。" : "已收到新的会话回答。");
}

function handleStreamEvent(event) {
  if (event.type === "error") {
    throw new Error(event.message || `流式失败，错误代码：${event.code || "unknown"}`);
  }
  if (event.message) {
    setStatus(event.message);
  }
  if (event.type === "completed") {
    return event.assistant;
  }
  return null;
}

async function typewriteMessage(cardElement, assistantData) {
  const scrollThread = () => {
    elements.conversationThread.scrollTop = elements.conversationThread.scrollHeight;
  };

  const rail = cardElement.querySelector(".assistant-rail");
  rail.innerHTML = "";

  if (assistantData.correction_notice) {
    const hint = document.createElement("div");
    hint.className = "assistant-hint";
    hint.innerHTML = `
      <span class="assistant-eyebrow">Correction Hint</span>
      <span class="assistant-hint-copy"></span>
    `;
    hint.querySelector(".assistant-hint-copy").textContent = assistantData.correction_notice;
    rail.appendChild(hint);
  }

  const title = document.createElement("h3");
  title.className = "assistant-title";
  title.textContent = "回答";
  rail.appendChild(title);

  const copy = document.createElement("p");
  copy.className = "assistant-copy";
  copy.setAttribute("data-testid", "assistant-copy");
  rail.appendChild(copy);

  for (const char of assistantData.answer) {
    copy.textContent += char;
    scrollThread();
    await new Promise((r) => setTimeout(r, 15));
  }

  if (assistantData.legal_basis?.length) {
    const basis = document.createElement("ul");
    basis.className = "basis-list";
    basis.setAttribute("data-testid", "basis-list");
    rail.appendChild(basis);
    for (const item of assistantData.legal_basis) {
      const rowItem = document.createElement("li");
      basis.appendChild(rowItem);
      for (const char of item) {
        rowItem.textContent += char;
        if (Math.random() > 0.5) scrollThread();
        await new Promise((r) => setTimeout(r, 10));
      }
    }
  }

  if (assistantData.clause_texts?.length) {
    const evidence = document.createElement("section");
    evidence.className = "evidence-panel";
    evidence.innerHTML = `
      <div class="evidence-head">
        <h4 class="evidence-title">证据区</h4>
        <span class="evidence-tag">SOURCE VERIFIED</span>
      </div>
      <div class="evidence-grid"></div>
    `;
    const grid = evidence.querySelector(".evidence-grid");
    rail.appendChild(evidence);
    
    for (const item of assistantData.clause_texts) {
      const card = document.createElement("article");
      card.className = "evidence-card";
      card.setAttribute("data-testid", "evidence-card");
      card.innerHTML = `
        <p class="evidence-path" data-testid="evidence-path"></p>
        <p class="evidence-copy" data-testid="evidence-copy"></p>
      `;
      grid.appendChild(card);
      const pathEl = card.querySelector(".evidence-path");
      pathEl.textContent = item.path;
      
      const textEl = card.querySelector(".evidence-copy");
      for (const char of item.text) {
        textEl.textContent += char;
        if (Math.random() > 0.8) scrollThread();
        await new Promise((r) => setTimeout(r, 5));
      }
    }
  }

  const meta = document.createElement("small");
  meta.className = "bubble-meta";
  meta.textContent = formatDateTime(assistantData.created_at) || "刚刚";
  rail.appendChild(meta);
  scrollThread();
}

function handleComposerSubmit(source) {
  const input = source === "home" ? elements.homeComposerInput : elements.threadComposerInput;
  const message = input?.value.trim() || "";
  if (!message) {
    showError("请输入问题后再发送。");
    return;
  }
  void sendMessage(message, source);
}

function bindComposerKeyboard(input, source) {
  input?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    if (event.shiftKey || event.isComposing || event.keyCode === 229) {
      return;
    }
    event.preventDefault();
    if (state.loading) {
      return;
    }
    handleComposerSubmit(source);
  });
}

elements.homeComposerForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  handleComposerSubmit("home");
});

elements.threadComposerForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  handleComposerSubmit("thread");
});

bindComposerKeyboard(elements.homeComposerInput, "home");
bindComposerKeyboard(elements.threadComposerInput, "thread");

elements.newConversationButton?.addEventListener("click", () => {
  hideError();
  goHome();
});

for (const trigger of document.querySelectorAll("[data-prompt]")) {
  trigger.addEventListener("click", () => {
    const prompt = trigger.getAttribute("data-prompt") || "";
    updateComposerValues(prompt);
    elements.homeComposerInput?.focus();
  });
}

window.addEventListener("popstate", () => {
  const routeConversationId = getRouteConversationId();
  if (!routeConversationId) {
    hideError();
    state.activeConversationId = null;
    state.activeDetail = null;
    setView("home");
    renderConversationList();
    renderThread();
    setStatus("已返回首页。");
    return;
  }
  void openConversation(routeConversationId, { push: false });
});

async function bootstrap() {
  setView(state.view);
  setStatus("正在加载页面。");
  try {
    await loadConversationList();
    const routeConversationId = getRouteConversationId() || initialConversationId || null;
    if (routeConversationId) {
      await openConversation(routeConversationId, { push: false });
      updateUrl(routeConversationId, { replace: true });
      return;
    }
    state.activeConversationId = null;
    state.activeDetail = null;
    setView("home");
    renderConversationList();
    renderThread();
    setStatus("首页已就绪，可以直接提问。");
  } catch (error) {
    showError(error instanceof Error ? error.message : "初始化失败。");
    setStatus("初始化失败。");
  }
}

void bootstrap();
