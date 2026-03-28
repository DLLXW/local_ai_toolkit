import DOMPurify from "dompurify";
import { marked } from "marked";
import "katex/dist/katex.min.css";
import renderMathInElement from "katex/contrib/auto-render";

const API_BASE = "http://localhost:8000/api";
const BACKEND_ORIGIN = new URL(API_BASE).origin;
const DISPLAY_MATH_PATTERN = /(?:^|\n)(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])(?:\n|$)/g;
const DISPLAY_MATH_FENCES = {
  "$$": "$$",
  "\\[": "\\]",
};
const INLINE_MATH_PATTERN = /(\\\([\s\S]*?\\\))|(?<!\$)(\$[^\n$]+?\$)(?!\$)/g;

marked.setOptions({
  gfm: true,
  breaks: false,
});

const appShell = document.querySelector("#appShell");
const readerEdgeHandle = document.querySelector("#readerEdgeHandle");
const navButtons = [...document.querySelectorAll("[data-module-nav]")];
const modulePanels = [...document.querySelectorAll("[data-module]")];
const readerRail = document.querySelector('[data-module-panel="reader"]');
const taskList = document.querySelector("#taskList");
const taskFilters = document.querySelector("#taskFilters");
const taskCountBadge = document.querySelector("#taskCountBadge");
const refreshTasksButton = document.querySelector("#refreshTasksButton");
const translateInput = document.querySelector("#translateInput");
const translateDirection = document.querySelector("#translateDirection");
const translateButton = document.querySelector("#translateButton");
const translateOutput = document.querySelector("#translateOutput");
const ocrFile = document.querySelector("#ocrFile");
const ocrButton = document.querySelector("#ocrButton");
const ocrOutput = document.querySelector("#ocrOutput");
const ocrMeta = document.querySelector("#ocrMeta");
const docFile = document.querySelector("#docFile");
const paperUrl = document.querySelector("#paperUrl");
const docButton = document.querySelector("#docButton");
const docDropzoneTitle = document.querySelector("#docDropzoneTitle");
const docDropzoneNote = document.querySelector("#docDropzoneNote");
const dropzoneCard = docFile?.closest(".dropzone-card");
const sourceTabs = [...document.querySelectorAll(".source-tab")];
const sourcePanels = [...document.querySelectorAll("[data-source-panel]")];
const taskMeta = document.querySelector("#taskMeta");
const taskOutput = document.querySelector("#taskOutput");
const readerMeta = document.querySelector("#readerMeta");
const resultOutput = document.querySelector("#resultOutput");
const modeButtons = [...document.querySelectorAll(".mode-button")];

let currentTaskId = null;
let currentDocName = null;
let currentMode = "bilingual";
let currentResult = null;
let allTasks = [];
let currentFilter = "all";
let currentModule = "reader";
let isUploadingDocument = false;
let isFocusMode = false;
let currentDocSource = "file";
let latestTaskStats = null;
const searchParams = new URLSearchParams(window.location.search);

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || JSON.stringify(payload));
  }
  return payload;
}

function renderMath(container) {
  if (!container) return;
  renderMathInElement(container, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
      { left: "$", right: "$", display: false },
    ],
    throwOnError: false,
  });
}

function setFocusMode(enabled) {
  isFocusMode = enabled;
  appShell.classList.toggle("focus-mode", enabled);
  if (readerEdgeHandle) {
    readerEdgeHandle.textContent = enabled ? "▸" : "◂";
  }
}

function setModule(moduleName) {
  currentModule = moduleName;
  for (const button of navButtons) {
    button.classList.toggle("active", button.dataset.moduleNav === moduleName);
  }
  for (const panel of modulePanels) {
    panel.classList.toggle("active", panel.dataset.module === moduleName);
  }
  if (readerRail) {
    readerRail.classList.toggle("hidden", moduleName !== "reader");
  }
  appShell.classList.toggle("reader-layout", moduleName === "reader");
  appShell.classList.toggle("single-layout", moduleName !== "reader");
  if (moduleName !== "reader") {
    setFocusMode(false);
  }
}

function getFilteredTasks(items) {
  if (currentFilter === "all") return items;
  return items.filter((task) => getTaskFolder(task) === currentFilter);
}

function getTaskFolder(task) {
  return task.folder_name || "未分类";
}

function getFolderGroups(items) {
  const counts = new Map();
  for (const task of items) {
    const folder = getTaskFolder(task);
    counts.set(folder, (counts.get(folder) || 0) + 1);
  }

  const folders = [...counts.entries()]
    .sort(([left], [right]) => {
      if (left === "未分类") return 1;
      if (right === "未分类") return -1;
      return left.localeCompare(right, "zh-CN");
    })
    .map(([id, count]) => ({ id, label: id, count }));

  return [{ id: "all", label: "全部文稿", count: items.length }, ...folders];
}

function renderFilters(items) {
  taskFilters.innerHTML = getFolderGroups(items)
    .map(
      (group) => `
        <button class="task-filter${group.id === currentFilter ? " active" : ""}" type="button" data-filter="${escapeHtml(group.id)}">
          <span>${escapeHtml(group.label)}</span>
          <span class="task-filter-count">${group.count}</span>
        </button>
      `,
    )
    .join("");
}

function taskStatusClass(status) {
  return ["done", "failed", "running", "queued"].includes(status) ? status : "";
}

function renderTaskList(items) {
  const filtered = getFilteredTasks(items);
  taskCountBadge.textContent = String(filtered.length);
  const folderOptions = getFolderGroups(items)
    .filter((folder) => folder.id !== "all")
    .map((folder) => folder.id);

  if (!filtered.length) {
    taskList.innerHTML = '<div class="reader-empty compact-empty"><div class="reader-empty-icon">🗃</div><h3>暂无文档</h3><p>当前筛选条件下还没有文稿记录。</p></div>';
    return;
  }

  taskList.innerHTML = filtered
    .map((task) => {
      const activeClass = task.id === currentTaskId ? " active" : "";
      const folderName = getTaskFolder(task);
      return `
        <article class="task-item${activeClass}">
          <div class="task-item-top">
            <div class="task-title-block">
              <strong>${escapeHtml(task.title)}</strong>
              <button class="mini-icon-button" type="button" data-edit-title="${task.id}" aria-label="编辑标题">✎</button>
            </div>
            <span class="task-status-pill ${taskStatusClass(task.status)}">${escapeHtml(task.status)}</span>
          </div>
          <div class="task-item-meta">
            <div>文件夹: ${escapeHtml(folderName)}</div>
            <div>文档: ${escapeHtml(task.doc_name || task.input_filename || "-")}</div>
            <div>阶段: ${escapeHtml(task.step || "-")}</div>
            <div>进度: ${Math.round((task.progress || 0) * 100)}%</div>
          </div>
          <div class="task-folder-row">
            <span class="task-folder-label">归类</span>
            <select class="task-folder-select" data-task-folder="${task.id}">
              ${folderOptions
                .map(
                  (folder) =>
                    `<option value="${escapeHtml(folder)}"${folder === folderName ? " selected" : ""}>${escapeHtml(folder)}</option>`,
                )
                .join("")}
              <option value="__new__">新建文件夹...</option>
            </select>
          </div>
          <div class="task-item-actions">
            <button class="task-action" type="button" data-open-task="${task.id}">打开</button>
            <button class="danger-action" type="button" data-delete-task="${task.id}">删除</button>
          </div>
        </article>
      `;
    })
    .join("");
}

async function refreshTasks() {
  try {
    const payload = await fetchJson(`${API_BASE}/tasks`);
    allTasks = payload.items;
    if (currentFilter !== "all" && !getFolderGroups(allTasks).some((folder) => folder.id === currentFilter)) {
      currentFilter = "all";
    }
    renderFilters(allTasks);
    renderTaskList(allTasks);
  } catch (error) {
    taskList.innerHTML = `<div class="plain-output">任务列表加载失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function updateTaskMetadata(taskId, changes) {
  const payload = await fetchJson(`${API_BASE}/task/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (currentTaskId === taskId) {
    renderTaskStatus(payload.task);
  }
  await refreshTasks();
}

function renderTaskStatus(task) {
  latestTaskStats = task;
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
      <div class="task-stat">
        <div class="task-stat-label">OCR 耗时</div>
        <div class="task-stat-value">${formatDuration(task.ocr_seconds)}</div>
      </div>
      <div class="task-stat">
        <div class="task-stat-label">翻译耗时</div>
        <div class="task-stat-value">${formatDuration(task.translation_seconds)}</div>
      </div>
      <div class="task-stat">
        <div class="task-stat-label">总耗时</div>
        <div class="task-stat-value">${formatDuration(task.total_seconds)}</div>
      </div>
    </div>
    <div class="progress-bar"><span style="width:${Math.round((task.progress || 0) * 100)}%"></span></div>
    ${task.error ? `<div class="hint-inline">失败原因: ${escapeHtml(task.error)}</div>` : ""}
  `;
  syncReaderTiming(task);
}

function sanitizeHtml(html) {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  });
}

function extractMathBlocks(markdown) {
  const placeholders = [];
  let rewritten = String(markdown || "");

  rewritten = rewritten.replace(DISPLAY_MATH_PATTERN, (match, block) => {
    const token = `MATHBLOCKTOKEN${placeholders.length}END`;
    placeholders.push({ token, block: block.trim(), display: true });
    return match.replace(block, token);
  });

  rewritten = rewritten.replace(INLINE_MATH_PATTERN, (match, parenBlock, dollarBlock) => {
    const block = (parenBlock || dollarBlock || "").trim();
    if (!block) return match;
    const token = `MATHINLINETOKEN${placeholders.length}END`;
    placeholders.push({ token, block, display: false });
    return token;
  });

  return { rewritten, placeholders };
}

function restoreMathBlocks(html, placeholders) {
  let restored = html;
  for (const { token, block, display } of placeholders) {
    const replacement = display
      ? `<div class="math-block">${escapeHtml(block)}</div>`
      : `<span class="math-inline">${escapeHtml(block)}</span>`;
    if (display) {
      restored = restored.split(`<p>${token}</p>`).join(replacement);
    }
    restored = restored.split(token).join(replacement);
  }
  return restored;
}

function normalizeAssetPaths(html, result) {
  const assetBaseUrl = result?.asset_base_url
    ? `${BACKEND_ORIGIN}${result.asset_base_url}`
    : result?.doc_name
      ? `${BACKEND_ORIGIN}/static/outputs/${encodeURIComponent(result.doc_name)}/imgs`
      : "";

  if (!assetBaseUrl) return html;

  return html
    .replaceAll('src="imgs/', `src="${assetBaseUrl}/`)
    .replaceAll("src='imgs/", `src='${assetBaseUrl}/`)
    .replaceAll('src="./imgs/', `src="${assetBaseUrl}/`)
    .replaceAll("src='./imgs/", `src='${assetBaseUrl}/`)
    .replaceAll('href="imgs/', `href="${assetBaseUrl}/`)
    .replaceAll("href='imgs/", `href='${assetBaseUrl}/`)
    .replaceAll('href="./imgs/', `href="${assetBaseUrl}/`)
    .replaceAll("href='./imgs/", `href='${assetBaseUrl}/`);
}

function renderMarkdownToHtml(markdown, result) {
  const { rewritten, placeholders } = extractMathBlocks(markdown || "");
  const rawHtml = marked.parse(rewritten);
  const restoredHtml = restoreMathBlocks(rawHtml, placeholders);
  return normalizeAssetPaths(sanitizeHtml(restoredHtml), result);
}

function renderRichContent(container, markdown, result) {
  container.innerHTML = `<div class="rendered-doc">${renderMarkdownToHtml(markdown, result)}</div>`;
  renderMath(container);
}

function splitMarkdownBlocks(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const blocks = [];
  let current = [];
  let inFence = false;
  let inHtmlTable = false;
  let inMathBlock = false;
  let mathCloser = "";

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

    if (inMathBlock) {
      current.push(line);
      if (stripped === mathCloser) {
        flushCurrent();
        inMathBlock = false;
        mathCloser = "";
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

    if (stripped === "$$" || stripped === "\\[") {
      flushCurrent();
      current.push(line);
      inMathBlock = true;
      mathCloser = stripped === "$$" ? "$$" : "\\]";
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
  return mergeSemanticBlocks(blocks);
}

function mergeSemanticBlocks(blocks) {
  const merged = [];
  let pending = [];

  const flushPending = () => {
    const block = pending.map((part) => part.trim()).filter(Boolean).join("\n\n").trim();
    if (block) merged.push(block);
    pending = [];
  };

  for (const block of blocks) {
    if (isRawBlock(block)) {
      flushPending();
      merged.push(block);
      continue;
    }

    if (isHeadingBlock(block)) {
      flushPending();
      pending = [block];
      continue;
    }

    if (pending.length) {
      pending.push(block);
      continue;
    }

    pending = [block];
    flushPending();
  }

  flushPending();
  return merged;
}

function isHeadingBlock(block) {
  return /^#{1,6}\s/.test(String(block || "").trim());
}

function isStandaloneRawLine(line) {
  return (
    line.startsWith("|") ||
    line.includes("![](") ||
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

function getMathFence(segment) {
  const source = String(segment?.source || "").trim();
  if (DISPLAY_MATH_FENCES[source]) {
    return { opener: source, closer: DISPLAY_MATH_FENCES[source] };
  }
  return null;
}

function stripOuterDisplayMath(content) {
  let normalized = String(content || "").trim();

  for (const [opener, closer] of Object.entries(DISPLAY_MATH_FENCES)) {
    if (normalized.startsWith(opener) && normalized.endsWith(closer)) {
      normalized = normalized.slice(opener.length, normalized.length - closer.length).trim();
      break;
    }
  }

  return normalized;
}

function normalizeDisplayMathContent(content) {
  return stripOuterDisplayMath(content)
    .replace(/\$(\\tag\{[^}]+\})\$/g, "$1")
    .replace(/\$([^$\n]+)\$/g, "$1")
    .trim();
}

function wrapDisplayMath(content, opener = "$$", closer = "$$") {
  const normalized = normalizeDisplayMathContent(content);
  return `${opener}\n${normalized}\n${closer}`;
}

function normalizeBilingualSegments(segments) {
  const normalized = [];

  for (let index = 0; index < segments.length; index += 1) {
    const current = segments[index];
    const fence = getMathFence(current);
    const middle = segments[index + 1];
    const tail = segments[index + 2];

    if (
      fence &&
      middle &&
      tail &&
      String(tail?.source || "").trim() === fence.closer &&
      (middle.kind === "text" || middle.kind === "raw")
    ) {
      normalized.push({
        kind: "math",
        source: wrapDisplayMath(middle.source, fence.opener, fence.closer),
        target: wrapDisplayMath(middle.target || middle.source, fence.opener, fence.closer),
      });
      index += 2;
      continue;
    }

    normalized.push(current);
  }

  return normalized;
}

function buildBilingualSegments(result) {
  if (Array.isArray(result.segments) && result.segments.length > 0) {
    return normalizeBilingualSegments(result.segments);
  }

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
            <div class="rendered-doc">${renderMarkdownToHtml(segment.source, result)}</div>
          </section>
        `;
      }

      if (segment.kind === "math") {
        return `
          <section class="bilingual-pair formula-pair">
            <div class="bilingual-col">
              <div class="bilingual-label">English</div>
              <div class="rendered-doc">${renderMarkdownToHtml(segment.source, result)}</div>
            </div>
            <div class="bilingual-col">
              <div class="bilingual-label">中文</div>
              <div class="rendered-doc">${renderMarkdownToHtml(segment.target, result)}</div>
            </div>
          </section>
        `;
      }

      return `
        <section class="bilingual-pair">
          <div class="bilingual-col">
            <div class="bilingual-label">English</div>
            <div class="rendered-doc">${renderMarkdownToHtml(segment.source, result)}</div>
          </div>
          <div class="bilingual-col">
            <div class="bilingual-label">中文</div>
            <div class="rendered-doc">${renderMarkdownToHtml(segment.target, result)}</div>
          </div>
        </section>
      `;
    })
    .join("");

  container.innerHTML = `<div class="bilingual-grid">${html}</div>`;
  renderMath(container);
}

function renderReaderEmpty() {
  resultOutput.innerHTML = `
    <div class="reader-empty">
      <div class="reader-empty-icon">📖</div>
      <h3>准备就绪</h3>
      <p>上传文档开始 OCR 解析与翻译，或从左侧历史记录中选择一份结果继续阅读。</p>
    </div>
  `;
}

function formatDuration(value) {
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return "—";
  if (value < 60) return `${value.toFixed(value >= 10 ? 1 : 2)} s`;
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return `${minutes}m ${seconds.toFixed(1)}s`;
}

function syncReaderTiming(task) {
  if (!task || !task.doc_name || task.doc_name !== currentDocName) return;
  const parts = [
    `当前文档: ${task.doc_name}`,
    `视图: ${labelForMode(currentMode)}`,
    `OCR: ${formatDuration(task.ocr_seconds)}`,
    `翻译: ${formatDuration(task.translation_seconds)}`,
  ];
  readerMeta.textContent = parts.join(" · ");
}

function renderCurrentResult() {
  if (!currentResult) {
    renderReaderEmpty();
    return;
  }

  if (currentMode === "english") {
    renderRichContent(resultOutput, currentResult.english_markdown, currentResult);
  } else if (currentMode === "chinese") {
    renderRichContent(resultOutput, currentResult.chinese_markdown, currentResult);
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
    if (latestTaskStats?.doc_name === docName) {
      syncReaderTiming(latestTaskStats);
    } else {
      readerMeta.textContent = `当前文档: ${docName} · 视图: ${labelForMode(currentMode)}`;
    }
    setModule("reader");
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
    if (latestTaskStats?.doc_name === currentDocName) {
      syncReaderTiming(latestTaskStats);
    } else {
      readerMeta.textContent = `当前文档: ${currentDocName} · 视图: ${labelForMode(currentMode)}`;
    }
  }
}

function updateSelectedDocumentState() {
  const file = docFile.files?.[0];
  if (!file) {
    dropzoneCard?.classList.remove("has-file");
    docDropzoneTitle.textContent = "拖拽文档到这里，或点击上方按钮选择";
    docDropzoneNote.textContent = "支持 PDF、PNG、JPG、JPEG。上传后会自动进入 OCR 与翻译流程。";
    return;
  }

  dropzoneCard?.classList.add("has-file");
  docDropzoneTitle.textContent = `已选择：${file.name}`;
  docDropzoneNote.textContent = `文件大小 ${(file.size / 1024 / 1024).toFixed(2)} MB，点击右侧“开始解析”后会立即创建任务。`;
  taskMeta.textContent = `已选择文件 ${file.name}，等待开始解析。`;
}

function updatePaperUrlState() {
  const url = paperUrl?.value.trim();
  if (!paperUrl) return;
  if (!url) {
    taskMeta.textContent = "输入 arXiv 链接后，系统会自动下载 PDF 并创建解析任务。";
    return;
  }
  taskMeta.textContent = `已输入论文链接，等待开始解析。`;
}

function setDocSource(source) {
  currentDocSource = source;
  for (const tab of sourceTabs) {
    tab.classList.toggle("active", tab.id === (source === "file" ? "sourceFileTab" : "sourceLinkTab"));
  }
  for (const panel of sourcePanels) {
    panel.classList.toggle("active", panel.dataset.sourcePanel === source);
  }
  if (source === "file") {
    updateSelectedDocumentState();
  } else {
    updatePaperUrlState();
  }
}

function setUploadingState(uploading) {
  isUploadingDocument = uploading;
  docButton.disabled = uploading;
  if (uploading) {
    docButton.textContent = currentDocSource === "link" ? "下载中..." : "上传中...";
    return;
  }
  docButton.textContent = "开始解析";
}

translateButton.addEventListener("click", async () => {
  if (!translateInput.value.trim()) {
    translateOutput.innerHTML = '<div class="reader-empty compact-empty"><div class="reader-empty-icon">🌐</div><h3>请输入内容</h3><p>输入一段文本后再发起翻译。</p></div>';
    return;
  }

  translateButton.disabled = true;
  translateButton.textContent = "翻译中...";
  translateOutput.innerHTML = '<div class="reader-empty compact-empty"><div class="reader-empty-icon">🌐</div><h3>正在翻译</h3><p>请稍候，结果马上回来。</p></div>';
  try {
    const payload = await fetchJson(`${API_BASE}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: translateInput.value.trim(),
        direction: translateDirection.value,
      }),
    });
    renderRichContent(translateOutput, payload.translated_text, null);
  } catch (error) {
    translateOutput.innerHTML = `<div class="plain-output">请求失败: ${escapeHtml(error.message)}</div>`;
  } finally {
    translateButton.disabled = false;
    translateButton.textContent = "立即翻译";
  }
});

ocrFile.addEventListener("change", () => {
  const file = ocrFile.files?.[0];
  ocrMeta.textContent = file
    ? `已选择 ${file.name}，点击“开始 OCR”发起识别。`
    : "支持图片和 PDF，识别完成后将在右侧展示 markdown 渲染结果。";
});

ocrButton.addEventListener("click", async () => {
  if (!ocrFile.files?.length) {
    ocrOutput.innerHTML = '<div class="plain-output">请先选择文件</div>';
    return;
  }

  ocrButton.disabled = true;
  ocrButton.textContent = "识别中...";
  ocrOutput.innerHTML = '<div class="reader-empty compact-empty"><div class="reader-empty-icon">🔎</div><h3>正在识别</h3><p>OCR 处理中，请稍候。</p></div>';
  const formData = new FormData();
  formData.append("file", ocrFile.files[0]);
  try {
    const payload = await fetchJson(`${API_BASE}/ocr`, {
      method: "POST",
      body: formData,
    });
    renderRichContent(ocrOutput, payload.markdown, null);
    ocrMeta.textContent = `识别完成：${ocrFile.files[0].name} · 耗时 ${formatDuration(payload.elapsed_seconds)}`;
  } catch (error) {
    ocrOutput.innerHTML = `<div class="plain-output">请求失败: ${escapeHtml(error.message)}</div>`;
  } finally {
    ocrButton.disabled = false;
    ocrButton.textContent = "开始 OCR";
  }
});

docFile.addEventListener("change", updateSelectedDocumentState);
paperUrl?.addEventListener("input", updatePaperUrlState);

for (const tab of sourceTabs) {
  tab.addEventListener("click", () => {
    setDocSource(tab.id === "sourceLinkTab" ? "link" : "file");
  });
}

docButton.addEventListener("click", async () => {
  setUploadingState(true);
  currentResult = null;
  renderCurrentResult();
  try {
    let payload;
    let displayName = "";

    if (currentDocSource === "file") {
      if (!docFile.files?.length) {
        taskMeta.textContent = "请先选择文档";
        return;
      }

      displayName = docFile.files[0].name;
      taskMeta.textContent = `正在上传 ${displayName}...`;
      taskOutput.innerHTML = `
        <div class="task-status-grid">
          <div class="task-stat"><div class="task-stat-label">任务状态</div><div class="task-stat-value">uploading</div></div>
          <div class="task-stat"><div class="task-stat-label">当前阶段</div><div class="task-stat-value">creating_task</div></div>
          <div class="task-stat"><div class="task-stat-label">文档名</div><div class="task-stat-value">${escapeHtml(displayName)}</div></div>
          <div class="task-stat"><div class="task-stat-label">用户感知</div><div class="task-stat-value">文件已提交</div></div>
        </div>
        <div class="progress-bar"><span style="width:12%"></span></div>
      `;

      const formData = new FormData();
      formData.append("file", docFile.files[0]);
      payload = await fetchJson(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });
    } else {
      const url = paperUrl?.value.trim();
      if (!url) {
        taskMeta.textContent = "请先输入 arXiv 链接";
        return;
      }

      displayName = url;
      taskMeta.textContent = "正在下载 arXiv 论文...";
      taskOutput.innerHTML = `
        <div class="task-status-grid">
          <div class="task-stat"><div class="task-stat-label">任务状态</div><div class="task-stat-value">downloading</div></div>
          <div class="task-stat"><div class="task-stat-label">当前阶段</div><div class="task-stat-value">fetching_pdf</div></div>
          <div class="task-stat"><div class="task-stat-label">文档来源</div><div class="task-stat-value">arXiv</div></div>
          <div class="task-stat"><div class="task-stat-label">用户感知</div><div class="task-stat-value">链接已提交</div></div>
        </div>
        <div class="progress-bar"><span style="width:12%"></span></div>
      `;
      payload = await fetchJson(`${API_BASE}/upload/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
    }

    currentTaskId = payload.task.id;
    taskMeta.textContent = `任务 ${payload.task.id} 已创建，正在解析 ${displayName}...`;
    await refreshTasks();
    await pollTask(payload.task.id);
  } catch (error) {
    taskMeta.textContent = `请求失败: ${error.message}`;
  } finally {
    setUploadingState(false);
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

  const editTitleId = target.dataset.editTitle;
  if (editTitleId) {
    const task = allTasks.find((item) => item.id === editTitleId);
    const nextTitle = window.prompt("输入新的文献标题", task?.title || "");
    if (nextTitle === null) return;
    try {
      await updateTaskMetadata(editTitleId, { title: nextTitle });
    } catch (error) {
      taskMeta.textContent = `标题更新失败: ${error.message}`;
    }
    return;
  }

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
        renderReaderEmpty();
        readerMeta.textContent = "从左侧文档列表中打开一个任务，即可在这里阅读结果。";
      }
      await refreshTasks();
    } catch (error) {
      taskMeta.textContent = `删除失败: ${error.message}`;
    }
  }
});

taskList.addEventListener("change", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement)) return;
  const taskId = target.dataset.taskFolder;
  if (!taskId) return;

  let nextFolder = target.value;
  if (nextFolder === "__new__") {
    const createdFolder = window.prompt("输入新的文件夹名称", "");
    if (createdFolder === null) {
      await refreshTasks();
      return;
    }
    nextFolder = createdFolder;
  }

  try {
    await updateTaskMetadata(taskId, { folder_name: nextFolder });
  } catch (error) {
    taskMeta.textContent = `文件夹更新失败: ${error.message}`;
    await refreshTasks();
  }
});

taskFilters.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const button = target.closest("[data-filter]");
  if (!(button instanceof HTMLElement)) return;
  currentFilter = button.dataset.filter || "all";
  renderFilters(allTasks);
  renderTaskList(allTasks);
});

refreshTasksButton.addEventListener("click", () => {
  refreshTasks();
});

for (const button of navButtons) {
  button.addEventListener("click", () => {
    setModule(button.dataset.moduleNav || "reader");
  });
}

readerEdgeHandle?.addEventListener("click", () => {
  if (currentModule !== "reader") return;
  setFocusMode(!isFocusMode);
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

refreshTasks();
renderReaderEmpty();
updateSelectedDocumentState();
updatePaperUrlState();
setDocSource("file");

const initialMode = searchParams.get("mode");
if (initialMode && ["english", "chinese", "bilingual"].includes(initialMode)) {
  setActiveMode(initialMode);
}

const initialTaskId = searchParams.get("task");
const initialDocName = searchParams.get("doc");
const initialModule = searchParams.get("module");

if (initialModule && ["reader", "ocr", "translate"].includes(initialModule)) {
  setModule(initialModule);
}

if (searchParams.get("focus") === "1" && currentModule === "reader") {
  setFocusMode(true);
}

if (initialTaskId) {
  pollTask(initialTaskId).catch((error) => {
    taskMeta.textContent = `任务加载失败: ${error.message}`;
  });
} else if (initialDocName) {
  loadResult(initialDocName).catch((error) => {
    readerMeta.textContent = `结果加载失败: ${error.message}`;
  });
}
