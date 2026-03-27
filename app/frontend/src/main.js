import DOMPurify from "dompurify";
import { marked } from "marked";

const API_BASE = "http://localhost:8000/api";
const STATIC_OUTPUTS_BASE = "http://localhost:8000/static/outputs";

marked.setOptions({
  gfm: true,
  breaks: false,
});

const healthStatus = document.querySelector("#healthStatus");
const taskList = document.querySelector("#taskList");
const refreshTasksButton = document.querySelector("#refreshTasksButton");
const translateInput = document.querySelector("#translateInput");
const translateDirection = document.querySelector("#translateDirection");
const translateButton = document.querySelector("#translateButton");
const translateOutput = document.querySelector("#translateOutput");
const ocrFile = document.querySelector("#ocrFile");
const ocrButton = document.querySelector("#ocrButton");
const ocrOutput = document.querySelector("#ocrOutput");
const docFile = document.querySelector("#docFile");
const docButton = document.querySelector("#docButton");
const taskMeta = document.querySelector("#taskMeta");
const taskOutput = document.querySelector("#taskOutput");
const readerMeta = document.querySelector("#readerMeta");
const resultOutput = document.querySelector("#resultOutput");
const modeButtons = [...document.querySelectorAll(".mode-button")];

let currentTaskId = null;
let currentDocName = null;
let currentMode = "bilingual";
let currentResult = null;
const searchParams = new URLSearchParams(window.location.search);

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || JSON.stringify(payload));
  }
  return payload;
}

async function refreshHealth() {
  try {
    const payload = await fetchJson(`${API_BASE}/health`);
    healthStatus.textContent = `${payload.status} · ${payload.environment}`;
  } catch (error) {
    healthStatus.textContent = `Unavailable · ${error.message}`;
  }
}

function renderTaskList(items) {
  if (!items.length) {
    taskList.innerHTML = '<div class="task-item-meta">还没有任务，先上传一份文档试试。</div>';
    return;
  }

  taskList.innerHTML = items
    .map((task) => {
      const activeClass = task.id === currentTaskId ? " active" : "";
      return `
        <article class="task-item${activeClass}">
          <strong>${escapeHtml(task.title)}</strong>
          <div class="task-item-meta">
            状态: ${escapeHtml(task.status)} · 进度: ${Math.round((task.progress || 0) * 100)}%<br/>
            阶段: ${escapeHtml(task.step || "-")}<br/>
            文档: ${escapeHtml(task.doc_name || task.input_filename || "-")}
          </div>
          <div class="task-item-actions">
            <button data-open-task="${task.id}">打开</button>
            <button class="secondary" data-delete-task="${task.id}">删除</button>
          </div>
        </article>
      `;
    })
    .join("");
}

async function refreshTasks() {
  try {
    const payload = await fetchJson(`${API_BASE}/tasks`);
    renderTaskList(payload.items);
  } catch (error) {
    taskList.innerHTML = `<div class="task-item-meta">任务列表加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

function renderTaskStatus(task) {
  taskOutput.innerHTML = `
    <div class="task-status-grid">
      <div class="task-stat">
        <div class="task-stat-label">任务状态</div>
        <div class="task-stat-value">${escapeHtml(task.status)}</div>
      </div>
      <div class="task-stat">
        <div class="task-stat-label">当前阶段</div>
        <div class="task-stat-value">${escapeHtml(task.step || "-")}</div>
      </div>
      <div class="task-stat">
        <div class="task-stat-label">文档名</div>
        <div class="task-stat-value">${escapeHtml(task.doc_name || task.input_filename || "-")}</div>
      </div>
      <div class="task-stat">
        <div class="task-stat-label">任务 ID</div>
        <div class="task-stat-value">${escapeHtml(task.id)}</div>
      </div>
    </div>
    <div class="progress-bar"><span style="width:${Math.round((task.progress || 0) * 100)}%"></span></div>
    ${task.error ? `<div class="hint" style="margin-top:14px;">失败原因: ${escapeHtml(task.error)}</div>` : ""}
  `;
}

function sanitizeHtml(html) {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  });
}

function normalizeAssetPaths(html, docName) {
  if (!docName) return html;
  const docBase = `${STATIC_OUTPUTS_BASE}/${encodeURIComponent(docName)}`;
  return html
    .replaceAll('src="imgs/', `src="${docBase}/imgs/`)
    .replaceAll("src='imgs/", `src='${docBase}/imgs/`)
    .replaceAll('src="./imgs/', `src="${docBase}/imgs/`)
    .replaceAll("src='./imgs/", `src='${docBase}/imgs/`)
    .replaceAll('href="imgs/', `href="${docBase}/imgs/`)
    .replaceAll("href='imgs/", `href='${docBase}/imgs/`)
    .replaceAll('href="./imgs/', `href="${docBase}/imgs/`)
    .replaceAll("href='./imgs/", `href='${docBase}/imgs/`);
}

function renderMarkdownToHtml(markdown, docName) {
  const rawHtml = marked.parse(markdown || "");
  return normalizeAssetPaths(sanitizeHtml(rawHtml), docName);
}

function renderRichContent(container, markdown, docName) {
  container.innerHTML = `<div class="rendered-doc">${renderMarkdownToHtml(markdown, docName)}</div>`;
}

function splitMarkdownBlocks(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const blocks = [];
  let current = [];
  let inFence = false;
  let inHtmlTable = false;

  const flushCurrent = () => {
    const block = current.join("\n").trim();
    if (block) blocks.push(block);
    current = [];
  };

  for (const line of lines) {
    const stripped = line.trim();

    if (inFence) {
      current.push(line);
      if (stripped.startsWith("```")) {
        flushCurrent();
        inFence = false;
      }
      continue;
    }

    if (inHtmlTable) {
      current.push(line);
      if (stripped.toLowerCase().includes("</table>")) {
        flushCurrent();
        inHtmlTable = false;
      }
      continue;
    }

    if (!stripped) {
      flushCurrent();
      continue;
    }

    if (stripped.startsWith("```")) {
      flushCurrent();
      current.push(line);
      inFence = true;
      continue;
    }

    if (stripped.toLowerCase().startsWith("<table")) {
      flushCurrent();
      current.push(line);
      if (stripped.toLowerCase().includes("</table>")) {
        flushCurrent();
      } else {
        inHtmlTable = true;
      }
      continue;
    }

    if (isStandaloneRawLine(stripped)) {
      flushCurrent();
      blocks.push(stripped);
      continue;
    }

    current.push(line);
  }

  flushCurrent();
  return blocks;
}

function isStandaloneRawLine(line) {
  return (
    line.startsWith("|") ||
    line.includes("![](") ||
    line.includes("$$") ||
    line.includes("\\[") ||
    line.includes("\\begin{")
  );
}

function isRawBlock(block) {
  const stripped = String(block || "").trim();
  return (
    stripped.startsWith("```") ||
    stripped.startsWith("|") ||
    stripped.toLowerCase().startsWith("<table") ||
    stripped.includes("![](") ||
    stripped.includes("$$") ||
    stripped.includes("\\[") ||
    stripped.includes("\\begin{")
  );
}

function buildBilingualSegments(result) {
  const englishBlocks = splitMarkdownBlocks(result.english_markdown);
  const chineseBlocks = splitMarkdownBlocks(result.chinese_markdown);

  if (englishBlocks.length === chineseBlocks.length && englishBlocks.length > 0) {
    return englishBlocks.map((source, index) => {
      const target = chineseBlocks[index] || "";
      if (isRawBlock(source)) {
        return {
          kind: "raw",
          source,
          target: isRawBlock(target) ? target : source,
        };
      }
      return { kind: "text", source, target };
    });
  }

  return result.segments || [];
}

function renderBilingualResult(container, result) {
  const html = buildBilingualSegments(result)
    .map((segment) => {
      if (segment.kind === "raw") {
        return `
          <section class="bilingual-raw">
            <div class="bilingual-label">Shared Block</div>
            <div class="rendered-doc">${renderMarkdownToHtml(segment.source, result.doc_name)}</div>
          </section>
        `;
      }

      return `
        <section class="bilingual-pair">
          <div class="bilingual-col">
            <div class="bilingual-label">English</div>
            <div class="rendered-doc">${renderMarkdownToHtml(segment.source, result.doc_name)}</div>
          </div>
          <div class="bilingual-col">
            <div class="bilingual-label">中文</div>
            <div class="rendered-doc">${renderMarkdownToHtml(segment.target, result.doc_name)}</div>
          </div>
        </section>
      `;
    })
    .join("");

  container.innerHTML = `<div class="bilingual-grid">${html}</div>`;
}

function renderCurrentResult() {
  if (!currentResult) {
    resultOutput.innerHTML = "";
    return;
  }

  if (currentMode === "english") {
    renderRichContent(resultOutput, currentResult.english_markdown, currentResult.doc_name);
  } else if (currentMode === "chinese") {
    renderRichContent(resultOutput, currentResult.chinese_markdown, currentResult.doc_name);
  } else {
    renderBilingualResult(resultOutput, currentResult);
  }
}

async function loadResult(docName) {
  currentDocName = docName;
  readerMeta.textContent = `正在加载 ${docName} 的 ${labelForMode(currentMode)} 结果...`;
  try {
    currentResult = await fetchJson(`${API_BASE}/result/${encodeURIComponent(docName)}`);
    renderCurrentResult();
    readerMeta.textContent = `当前文档: ${docName} · 视图: ${labelForMode(currentMode)}`;
  } catch (error) {
    currentResult = null;
    resultOutput.innerHTML = `<div class="plain-output">结果加载失败: ${escapeHtml(error.message)}</div>`;
    readerMeta.textContent = `当前文档: ${docName}`;
  }
}

function setActiveMode(mode) {
  currentMode = mode;
  for (const button of modeButtons) {
    button.classList.toggle("active", button.dataset.mode === mode);
  }
  renderCurrentResult();
  if (currentDocName) {
    readerMeta.textContent = `当前文档: ${currentDocName} · 视图: ${labelForMode(currentMode)}`;
  }
}

translateButton.addEventListener("click", async () => {
  translateOutput.textContent = "翻译中...";
  try {
    const payload = await fetchJson(`${API_BASE}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: translateInput.value.trim(),
        direction: translateDirection.value,
      }),
    });
    translateOutput.textContent = payload.translated_text;
  } catch (error) {
    translateOutput.textContent = `请求失败: ${error.message}`;
  }
});

ocrButton.addEventListener("click", async () => {
  if (!ocrFile.files?.length) {
    ocrOutput.innerHTML = '<div class="plain-output">请先选择文件</div>';
    return;
  }
  ocrOutput.innerHTML = '<div class="plain-output">OCR 处理中...</div>';
  const formData = new FormData();
  formData.append("file", ocrFile.files[0]);
  try {
    const payload = await fetchJson(`${API_BASE}/ocr`, {
      method: "POST",
      body: formData,
    });
    renderRichContent(ocrOutput, payload.markdown, "");
  } catch (error) {
    ocrOutput.innerHTML = `<div class="plain-output">请求失败: ${escapeHtml(error.message)}</div>`;
  }
});

docButton.addEventListener("click", async () => {
  if (!docFile.files?.length) {
    taskMeta.textContent = "请先选择文档";
    return;
  }
  taskMeta.textContent = "上传中...";
  resultOutput.innerHTML = "";
  const formData = new FormData();
  formData.append("file", docFile.files[0]);
  try {
    const payload = await fetchJson(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
    });
    currentTaskId = payload.task.id;
    taskMeta.textContent = `任务 ${payload.task.id} 已创建`;
    await pollTask(payload.task.id);
  } catch (error) {
    taskMeta.textContent = `请求失败: ${error.message}`;
  }
});

async function pollTask(taskId) {
  currentTaskId = taskId;
  for (;;) {
    const payload = await fetchJson(`${API_BASE}/task/${taskId}`);
    const task = payload.task;
    renderTaskStatus(task);
    await refreshTasks();
    if (task.status === "done") {
      if (task.doc_name) {
        await loadResult(task.doc_name);
      }
      taskMeta.textContent = `任务 ${task.id} 已完成`;
      return;
    }
    if (task.status === "failed") {
      resultOutput.innerHTML = `<div class="plain-output">任务失败: ${escapeHtml(task.error || "unknown error")}</div>`;
      taskMeta.textContent = `任务 ${task.id} 失败`;
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
}

taskList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const openTaskId = target.dataset.openTask;
  if (openTaskId) {
    await pollTask(openTaskId);
    return;
  }

  const deleteTaskId = target.dataset.deleteTask;
  if (deleteTaskId) {
    try {
      await fetchJson(`${API_BASE}/task/${deleteTaskId}`, { method: "DELETE" });
      if (currentTaskId === deleteTaskId) {
        currentTaskId = null;
        currentDocName = null;
        currentResult = null;
        taskOutput.innerHTML = "";
        resultOutput.innerHTML = "";
        readerMeta.textContent = "选择一个任务即可查看结果。";
      }
      await refreshTasks();
    } catch (error) {
      taskMeta.textContent = `删除失败: ${error.message}`;
    }
  }
});

refreshTasksButton.addEventListener("click", () => {
  refreshTasks();
});

for (const button of modeButtons) {
  button.addEventListener("click", () => {
    setActiveMode(button.dataset.mode);
  });
}

function labelForMode(mode) {
  return (
    {
      english: "English",
      chinese: "中文",
      bilingual: "双语",
    }[mode] || mode
  );
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

refreshHealth();
refreshTasks();

const initialMode = searchParams.get("mode");
if (initialMode && ["english", "chinese", "bilingual"].includes(initialMode)) {
  setActiveMode(initialMode);
}

const initialTaskId = searchParams.get("task");
const initialDocName = searchParams.get("doc");

if (initialTaskId) {
  pollTask(initialTaskId).catch((error) => {
    taskMeta.textContent = `任务加载失败: ${error.message}`;
  });
} else if (initialDocName) {
  loadResult(initialDocName).catch((error) => {
    readerMeta.textContent = `结果加载失败: ${error.message}`;
  });
}
