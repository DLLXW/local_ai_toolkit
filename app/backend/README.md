# Local AI Toolkit Backend

当前阶段已经具备最小可验证链路：

- `GET /api/health`
- `POST /api/ocr`
- `POST /api/translate`
- `POST /api/upload`
- `GET /api/task/{id}`
- `GET /api/tasks`
- `GET /api/result/{doc_name}`

## 运行方式

```bash
cd app/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 外部依赖

- OCR 服务：`http://127.0.0.1:8080/chat/completions`
- 翻译服务：`http://127.0.0.1:8090/v1/chat/completions`
- GLM-OCR CLI：`../glm-ocr/.venv/bin/glmocr`

## 文档翻译链路

1. 上传 PDF 或图片到 `/api/upload`
2. 后端保存文件并创建任务
3. 后台任务调用 `glmocr parse`
4. 读取 OCR 输出 markdown/json
5. 按段翻译文本块，跳过代码块/公式/表格/图片块
6. 输出：
   - `*.zh.md`
   - `*.bilingual.md`
   - `*.bilingual.json`
