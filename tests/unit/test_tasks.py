import importlib
import os
import sys
from pathlib import Path


def _reload_tasks(db_url: str):
    os.environ["TASKS_DB_URL"] = db_url
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    if "core.tasks" in sys.modules:
        del sys.modules["core.tasks"]
    return importlib.import_module("core.tasks")


def test_create_and_crud(tmp_path):
    db_file = tmp_path / "tasks.db"
    tasks = _reload_tasks(f"sqlite:///{db_file}")

    record = tasks.create_task("email", ["name"], "alice@example.com")
    task_id = record["id"]
    assert record["status"] == "pending"

    fetched = tasks.get_task(task_id)
    assert fetched["trigger"] == "email"
    assert fetched["missing_fields"] == ["name"]

    updated = tasks.update_task_status(task_id, "done")
    assert updated["status"] == "done"

    all_tasks = tasks.list_tasks()
    assert len(all_tasks) == 1

    assert tasks.delete_task(task_id) is True
    assert tasks.get_task(task_id) is None
