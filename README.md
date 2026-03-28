# Local AI Toolkit

Local AI Toolkit is a local-first document workflow for OCR, translation, and bilingual reading.
It is designed for users who want to run the full pipeline on their own machine and inspect long-form documents in a cleaner workspace.

当前版本已经具备三条核心能力：

- `OCR 识别`：调用本地 OCR 模型，将图片或 PDF 识别为 Markdown
- `翻译器`：调用本地翻译模型，支持中英双向翻译
- `文献阅读`：上传文档后自动完成 OCR 与翻译，并在前端进行原文 / 中文 / 中英对照阅读

## Features

- Local-first architecture: OCR、翻译、应用界面均可在本地环境运行
- Reader workflow: 支持文档上传、任务队列、结果轮询、阅读视图切换
- Bilingual reading: 支持英文原文、中文结果与中英对照阅读
- Markdown-aware rendering: 兼顾标题、段落、表格、图片、代码块与公式
- arXiv import: 支持通过 arXiv 链接下载论文并进入文献阅读流程
- Folder management: 支持文档分类、文件夹重命名与删除
- Timing stats: 前端展示 OCR、翻译与总耗时

## Project Structure

```text
.
├── app/
│   ├── backend/      # FastAPI backend
│   ├── frontend/     # Vite frontend
│   ├── scripts/      # Local development scripts
│   └── data/         # Runtime uploads / outputs / task metadata
├── start_ocr_server.sh
├── start-hy-mt.sh
└── .gitignore
```

## Architecture

The repository is split into two layers:

1. Model service layer
   - OCR service
   - translation service
2. Application layer
   - `app/backend`: API, task orchestration, result management
   - `app/frontend`: reading workspace and tool UI

The application assumes OCR and translation model services are already available locally through HTTP APIs.

## Tech Stack

- Backend: FastAPI, httpx, pydantic-settings
- Frontend: Vite, vanilla JavaScript, marked, KaTeX, DOMPurify
- Python: `uv` for environment management

## Requirements

- Python `3.11+`
- Node.js `18+`
- `uv`
- A running OCR model service
- A running translation model service

## Quick Start

### 1. Start model services

Start your local OCR service:

```bash
./start_ocr_server.sh
```

Start your local translation service:

```bash
./start-hy-mt.sh
```

### 2. Start the backend

Create the virtual environment in `app/.venv` and install backend dependencies:

```bash
uv venv app/.venv
app/.venv/bin/pip install \
  fastapi \
  httpx \
  pydantic-settings \
  python-multipart \
  uvicorn

cp app/backend/.env.example app/backend/.env
cd app/frontend && npm install && cd ../..
```

Then run the backend:

```bash
./app/scripts/dev_backend.sh
```

### 3. Start the frontend

```bash
./app/scripts/dev_frontend.sh
```

### 4. Open the app

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health check: `http://localhost:8000/api/health`

## Configuration

Backend configuration lives in `app/backend/.env.example`.

Important variables:

- `LOCAL_AI_OCR_BASE_URL`
- `LOCAL_AI_OCR_CHAT_PATH`
- `LOCAL_AI_OCR_MODEL`
- `LOCAL_AI_TRANSLATE_BASE_URL`
- `LOCAL_AI_TRANSLATE_CHAT_PATH`
- `LOCAL_AI_TRANSLATE_MODEL`
- `LOCAL_AI_TRANSLATE_RETRY_ATTEMPTS`
- `LOCAL_AI_TRANSLATE_MAX_CHARS_PER_CHUNK`

## API Overview

Current backend endpoints include:

- `GET /api/health`
- `POST /api/ocr`
- `POST /api/translate`
- `POST /api/upload`
- `POST /api/upload/url`
- `GET /api/tasks`
- `GET /api/task/{id}`
- `PATCH /api/task/{id}`
- `PATCH /api/folder/rename`
- `POST /api/folder/delete`
- `GET /api/result/{doc_name}`

## Current Scope

This project is currently focused on a local reading workflow rather than a general-purpose AI platform.

The current product direction emphasizes:

- academic papers
- scanned PDFs
- OCR-to-translation pipelines
- structured reading and comparison

## Non-Commercial License

This repository is released with a **source-available, non-commercial license**.

- Personal use: allowed
- Research use: allowed
- Educational use: allowed
- Commercial use: not allowed
- Selling, relicensing, paid hosting, or using this project inside commercial products or services: not allowed

See `LICENSE` for the full terms.

Important note:
Because commercial use is prohibited, this license is **not an OSI-approved open-source license** in the strict legal sense.
It is public source code with non-commercial restrictions.

## Roadmap

- More robust OCR / translation pipeline management
- Better document import and organization
- Improved reading experience for formula-heavy papers
- More polished deployment and release workflow

## Contributing

Issues and discussion are welcome.

If you want to contribute code, please open an issue first for non-trivial changes so the direction can stay aligned with the project roadmap.

## Acknowledgements

This project is built around a local model workflow and depends on separately running OCR / translation model services.
Please also review the upstream licenses and usage terms of any model weights or external services you use together with this repository.
