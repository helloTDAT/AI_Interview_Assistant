from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models import ReviewAnnotation, ReviewReport, TaskRecord, UserPublic, UserRole


def _now() -> str:
    return datetime.utcnow().isoformat()


class ReviewDatabase:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or settings.database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True) if self.path.parent != Path(".") else None
        self.init_schema()
        self.seed_users()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS annotations (
                    id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    segment_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def seed_users(self) -> None:
        defaults = [
            ("student-demo", "student", "student123", UserRole.student, "学生 Demo"),
            ("teacher-demo", "teacher", "teacher123", UserRole.teacher, "讲师 Demo"),
            ("admin-demo", "admin", "admin123", UserRole.admin, "管理员 Demo"),
        ]
        with self.connect() as conn:
            for user_id, username, password, role, display_name in defaults:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (id, username, password_hash, role, display_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, username, self.hash_password(password), role.value, display_name, _now()),
                )

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(f"ai-interview:{password}".encode("utf-8")).hexdigest()

    def login(self, username: str, password: str) -> tuple[str, UserPublic] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not row or row["password_hash"] != self.hash_password(password):
                return None
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, row["id"], _now()),
            )
            return token, self._user_from_row(row)

    def logout(self, token: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def user_for_token(self, token: str) -> UserPublic | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
            return self._user_from_row(row) if row else None

    def save_task(self, task: TaskRecord, owner_user_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, owner_user_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (task.id, owner_user_id, json.dumps(task.model_dump(mode="json"), ensure_ascii=False)),
            )

    def list_tasks(self, user: UserPublic) -> list[TaskRecord]:
        query = "SELECT payload FROM tasks"
        params: tuple[Any, ...] = ()
        if user.role == UserRole.student:
            query += " WHERE owner_user_id = ?"
            params = (user.id,)
        query += " ORDER BY json_extract(payload, '$.created_at') DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [TaskRecord(**json.loads(row["payload"])) for row in rows]

    def save_review(self, review: ReviewReport) -> None:
        review.updated_at = datetime.utcnow()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reviews (id, task_id, owner_user_id, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (
                    review.id,
                    review.task_id,
                    review.owner_user_id,
                    json.dumps(review.model_dump(mode="json"), ensure_ascii=False),
                ),
            )

    def get_review(self, review_id: str) -> ReviewReport | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return ReviewReport(**json.loads(row["payload"])) if row else None

    def add_annotation(self, annotation: ReviewAnnotation) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO annotations (id, review_id, segment_id, author_id, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    annotation.id,
                    annotation.review_id,
                    annotation.segment_id,
                    annotation.author_id,
                    json.dumps(annotation.model_dump(mode="json"), ensure_ascii=False),
                ),
            )

    def _user_from_row(self, row: sqlite3.Row) -> UserPublic:
        return UserPublic(id=row["id"], username=row["username"], role=UserRole(row["role"]), display_name=row["display_name"])


review_db = ReviewDatabase()
