from __future__ import annotations

import uuid


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}
        self._session_project: dict[str, uuid.UUID] = {}

    def create_session(self, project_id: uuid.UUID) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        self._session_project[session_id] = project_id
        return session_id

    def get_session(self, session_id: str) -> list[dict] | None:
        return self._sessions.get(session_id)

    def get_messages(self, session_id: str) -> list[dict]:
        return self._sessions.get(session_id, [])

    def add_message(self, session_id: str, message: dict) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def trim_history(self, session_id: str, max_messages: int = 40) -> None:
        messages = self._sessions.get(session_id, [])
        if len(messages) <= max_messages:
            return
        self._sessions[session_id] = messages[-max_messages:]

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._session_project.pop(session_id, None)
