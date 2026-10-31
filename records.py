"""Student records (JSON) and the 'who is asking' context.
A live copy is made in the runtime folder so the original sample data is never modified."""
import json
import shutil
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class Student:
    """The student the agent is currently helping. Every data tool is bound to this student."""
    user_id: str
    name: str


def _live():
    path = config.runtime_path("students_live.json")
    if not path.exists():
        shutil.copy(config.DATA_DIR / "students.json", path)
    return path


def _load() -> dict:
    return json.loads(_live().read_text(encoding="utf-8"))


def get(student_id: str):
    return _load().get((student_id or "").strip().upper())


def list_students() -> list:
    return [Student(sid, rec["name"]) for sid, rec in _load().items()]
