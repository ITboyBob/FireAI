const form = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const submitButton = document.getElementById("submit-button");
const requestStatus = document.getElementById("request-status");
const errorPanel = document.getElementById("error-panel");
const answerCard = document.getElementById("answer-card");
const answerPanel = document.getElementById("answer-panel");
const emptyState = answerPanel?.querySelector(".answer-empty");
const conclusionNode = document.getElementById("answer-conclusion");
const citationsNode = document.getElementById("answer-citations");
const scopeNode = document.getElementById("answer-scope");
const uncertaintyNode = document.getElementById("answer-uncertainty");
const evidenceNode = document.getElementById("answer-evidence");

function setLoadingState(isLoading) {
  if (!submitButton || !requestStatus) {
    return;
  }

  submitButton.disabled = isLoading;
  submitButton.textContent = isLoading ? "检索中..." : "提交问题";
  if (isLoading) {
    requestStatus.textContent = "正在请求 `/api/chat`。";
  }
}

function hideError() {
  if (!errorPanel) {
    return;
  }
  errorPanel.hidden = true;
  errorPanel.textContent = "";
}

function showError(message) {
  if (!errorPanel) {
    return;
  }
  errorPanel.hidden = false;
  errorPanel.textContent = message;
}

function renderTags(target, values) {
  if (!target) {
    return;
  }

  target.replaceChildren();
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    target.appendChild(item);
  }
}

function renderEvidence(evidence) {
  if (!evidenceNode) {
    return;
  }

  evidenceNode.replaceChildren();
  for (const item of evidence) {
    const row = document.createElement("li");
    const path = document.createElement("p");
    const text = document.createElement("p");

    path.className = "evidence-path";
    path.textContent = item.path || item.chunk_id;

    text.className = "evidence-text";
    text.textContent = item.text;

    row.append(path, text);
    evidenceNode.appendChild(row);
  }
}

function renderAnswer(payload) {
  if (!answerCard || !conclusionNode || !scopeNode || !uncertaintyNode) {
    return;
  }

  emptyState?.setAttribute("hidden", "");
  answerCard.hidden = false;
  conclusionNode.textContent = payload.conclusion || "";
  scopeNode.textContent = payload.scope || "未声明适用范围。";
  uncertaintyNode.textContent = payload.uncertainty || "未声明额外不确定点。";
  renderTags(citationsNode, payload.citations || []);
  renderEvidence(payload.evidence || []);
}

async function requestAnswer(message) {
  const endpoint = form?.dataset.chatEndpoint || "/api/chat";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ message }),
  });

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("服务端没有返回 JSON，无法渲染回答。");
  }

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败，状态码 ${response.status}`);
  }

  return payload;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();

  const message = questionInput?.value.trim() || "";
  if (!message) {
    showError("请输入问题后再提交。");
    return;
  }

  try {
    setLoadingState(true);
    const payload = await requestAnswer(message);
    renderAnswer(payload);
    if (requestStatus) {
      requestStatus.textContent = "已收到结构化回答。";
    }
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "请求失败。";
    showError(messageText);
    if (requestStatus) {
      requestStatus.textContent = "请求失败。";
    }
  } finally {
    setLoadingState(false);
  }
});

for (const chip of document.querySelectorAll(".prompt-chip")) {
  chip.addEventListener("click", () => {
    const prompt = chip.getAttribute("data-prompt") || "";
    if (!questionInput) {
      return;
    }
    questionInput.value = prompt;
    questionInput.focus();
  });
}
