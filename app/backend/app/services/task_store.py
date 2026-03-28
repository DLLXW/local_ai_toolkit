import json
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.task import TaskDetailResponse, TaskKind, TaskListResponse, TaskRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStore:
    def __init__(self, tasks_file: Path):
        self.tasks_file = tasks_file
        if not self.tasks_file.exists():
            self._write([])

    def list_tasks(self) -> TaskListResponse:
        items = [TaskRecord.model_validate(item) for item in self._read()]
        return TaskListResponse(items=items)

    def get_task(self, task_id: str) -> TaskDetailResponse | None:
        for item in self._read():
            if item.get("id") == task_id:
                return TaskDetailResponse(task=TaskRecord.model_validate(item))
        return None

    def create_task(
        self,
        *,
        task_id: str,
        title: str,
        kind: TaskKind,
        input_filename: str | None = None,
        doc_name: str | None = None,
        folder_name: str = "未分类",
    ) -> TaskRecord:
        now = utc_now()
        task = TaskRecord(
            id=task_id,
            kind=kind,
            status="queued",
            title=title,
            folder_name=folder_name,
            created_at=now,
            updated_at=now,
            input_filename=input_filename,
            doc_name=doc_name,
        )
        items = self._read()
        items.insert(0, task.model_dump(mode="json"))
        self._write(items)
        return task

    def update_task(self, task_id: str, **changes: object) -> TaskRecord:
        items = self._read()
        for index, item in enumerate(items):
            if item.get("id") != task_id:
                continue

            merged = {**item, **changes, "updated_at": utc_now().isoformat()}
            task = TaskRecord.model_validate(merged)
            items[index] = task.model_dump(mode="json")
            self._write(items)
            return task

        raise KeyError(f"Task not found: {task_id}")

    def delete_task(self, task_id: str) -> bool:
        items = self._read()
        kept = [item for item in items if item.get("id") != task_id]
        if len(kept) == len(items):
            return False
        self._write(kept)
        return True

    def rename_folder(self, old_name: str, new_name: str) -> int:
        items = self._read()
        renamed = 0
        for item in items:
            if (item.get("folder_name") or "未分类") != old_name:
                continue
            item["folder_name"] = new_name
            item["updated_at"] = utc_now().isoformat()
            renamed += 1
        if renamed:
            self._write(items)
        return renamed

    def clear_folder(self, folder_name: str, fallback_folder: str = "未分类") -> int:
        items = self._read()
        updated = 0
        for item in items:
            if (item.get("folder_name") or "未分类") != folder_name:
                continue
            item["folder_name"] = fallback_folder
            item["updated_at"] = utc_now().isoformat()
            updated += 1
        if updated:
            self._write(items)
        return updated

    def _read(self) -> list[dict]:
        try:
            return json.loads(self.tasks_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _write(self, items: list[dict]) -> None:
        self.tasks_file.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
