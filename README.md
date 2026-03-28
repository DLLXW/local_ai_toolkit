# Local AI Toolkit

一个面向本地环境的 OCR、翻译与文献阅读工具箱。

它的目标不是做一个“大而全”的 AI 平台，而是把一条非常明确的工作流打磨好：
把论文、扫描件或长文档接入本地 OCR 和翻译模型，再在一个更适合阅读的界面里完成查看、对照和整理。

## 演示

[![Local AI Toolkit Demo](./docs/demo.mp4.png)](./demo.mp4)

点击上方封面图可查看演示视频：[`demo.mp4`](./demo.mp4)

## 当前能力

- `OCR 识别`
  支持图片与 PDF 输入，输出 Markdown 结果
- `翻译器`
  支持英文译中文、中文译英文
- `文献阅读`
  支持文档上传、任务轮询、阅读模式切换、中英对照查看
- `arXiv 导入`
  支持通过 arXiv 链接下载论文并进入文献阅读流程
- `文件夹管理`
  支持文档分类、文件夹重命名与删除
- `耗时统计`
  前端展示 OCR、翻译与总耗时

## 项目特点

- `本地优先`
  OCR 服务、翻译服务和应用层都可以在本地运行
- `围绕阅读体验设计`
  重点面向论文、扫描文档和长文本，而不是通用聊天场景
- `Markdown / 公式 / 表格友好`
  针对技术文档与公式较多的内容做了较多渲染处理
- `工作流清晰`
  从上传、OCR、翻译到阅读都收敛在一套统一界面中

## 项目结构

```text
.
├── app/
│   ├── backend/      # FastAPI 后端
│   ├── frontend/     # Vite 前端
│   ├── scripts/      # 本地开发脚本
│   └── data/         # 运行时数据：上传、输出、任务元数据
├── start_ocr_server.sh
├── start-hy-mt.sh
├── parse-with-glmocr.sh
└── run-with-monitor.sh
```

## 架构说明

整个仓库可以理解为两层：

1. 模型服务层
   - OCR 服务
   - 翻译服务
2. 应用层
   - `app/backend`：API、任务编排、结果管理
   - `app/frontend`：工具界面、阅读界面、任务列表

当前应用默认假设：
你已经在本地准备好了 OCR 模型服务和翻译模型服务，并通过 HTTP 接口对外提供能力。

## 技术栈

- 后端：FastAPI、httpx、pydantic-settings
- 前端：Vite、原生 JavaScript、marked、KaTeX、DOMPurify
- Python 环境：`uv`

## 运行要求

- Python `3.11+`
- Node.js `18+`
- `uv`
- 可用的本地 OCR 服务
- 可用的本地翻译服务

## 快速开始

### 1. 启动模型服务

启动 OCR 服务：

```bash
./start_ocr_server.sh
```

启动翻译服务：

```bash
./start-hy-mt.sh
```

这两个脚本已经尽量做成了通用形式，但你仍然需要根据自己的本地模型路径调整环境变量，例如：

- `SERVER_DIR`
- `LLAMA_SERVER_BIN`
- `MODEL_PATH`

### 2. 准备后端环境

```bash
uv venv app/.venv

app/.venv/bin/pip install \
  fastapi \
  httpx \
  pydantic-settings \
  python-multipart \
  uvicorn

cp app/backend/.env.example app/backend/.env
```

### 3. 安装前端依赖

```bash
cd app/frontend
npm install
cd ../..
```

### 4. 启动后端

```bash
./app/scripts/dev_backend.sh
```

### 5. 启动前端

```bash
./app/scripts/dev_frontend.sh
```

### 6. 打开应用

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/api/health`

## 配置说明

后端环境变量示例见：

- `app/backend/.env.example`

比较关键的配置项包括：

- `LOCAL_AI_OCR_BASE_URL`
- `LOCAL_AI_OCR_CHAT_PATH`
- `LOCAL_AI_OCR_MODEL`
- `LOCAL_AI_TRANSLATE_BASE_URL`
- `LOCAL_AI_TRANSLATE_CHAT_PATH`
- `LOCAL_AI_TRANSLATE_MODEL`
- `LOCAL_AI_TRANSLATE_RETRY_ATTEMPTS`
- `LOCAL_AI_TRANSLATE_MAX_CHARS_PER_CHUNK`

## API 概览

当前后端主要接口包括：

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

## 当前适用场景

这个项目当前更适合以下任务：

- 论文阅读
- 扫描版 PDF 识别
- 英文技术文档翻译
- OCR 结果整理与二次阅读
- 中英对照精读

它目前并不追求：

- 通用浏览器抓取
- 商业级 SaaS 部署
- 多租户平台化能力
- 在线托管推理服务

## 许可证

本仓库使用一份“非商业使用”的源码许可证，完整条款见：

- [LICENSE](./LICENSE)

你可以：

- 个人使用
- 学术研究使用
- 教学使用
- 非商业修改与分发

你不可以：

- 直接或间接将本项目用于商业用途
- 将本项目接入付费产品或付费服务
- 将本项目作为商业服务的一部分进行托管、售卖或再授权

需要特别说明的是：
由于该许可证限制了商业使用，因此它并不属于严格法律意义上的 OSI 标准开源许可证，更准确地说，它是“公开源码 / source-available”项目。

## Roadmap

- 提升 OCR 与翻译链路的稳定性
- 改进公式密集型论文的阅读体验
- 优化文档管理与归档体验
- 完善部署与发布流程

## 贡献

欢迎提交 Issue 与讨论想法。

如果你想提交较大的代码改动，建议先开 Issue 对齐方向，以避免和项目当前路线偏离太远。

## 致谢

本项目建立在本地模型工作流之上，运行时依赖你自行部署的 OCR / 翻译模型服务。

如果你在本项目中使用了第三方模型权重、外部推理框架或其他工具，请同时关注它们各自的许可证与使用条款。
