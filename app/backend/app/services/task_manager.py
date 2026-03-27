import asyncio
from pathlib import Path

from app.core.settings import Settings
from app.services.document_pipeline import DocumentPipeline
from app.services.task_store import TaskStore


class TaskManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = TaskStore(settings.tasks_file)
        self._running: dict[str, asyncio.Task] = {}

    def start_document_task(self, task_id: str, input_path: Path, doc_name: str) -> None:
        if task_id in self._running:
            return
        task = asyncio.create_task(
            self._run_document_task(task_id=task_id, input_path=input_path, doc_name=doc_name)
        )
        self._running[task_id] = task
        task.add_done_callback(lambda _: self._running.pop(task_id, None))

    async def _run_document_task(self, *, task_id: str, input_path: Path, doc_name: str) -> None:
        pipeline = DocumentPipeline(self.settings)

        def update(changes: dict) -> None:
            self.store.update_task(task_id, **changes)

        try:
            update({"status": "running", "progress": 0.05, "step": "queued"})
            artifacts = await asyncio.to_thread(
                pipeline.run,
                input_path,
                doc_name=doc_name,
                update=update,
            )
            self.store.update_task(
                task_id,
                status="done",
                progress=1.0,
                step="completed",
                doc_name=artifacts.doc_name,
                result_path=str(artifacts.output_dir / f"{artifacts.doc_name}.bilingual.json"),
            )
        except Exception as exc:
            self.store.update_task(
                task_id,
                status="failed",
                step="failed",
                error=str(exc),
            )
