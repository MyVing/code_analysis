from __future__ import annotations

import uuid


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}
        self._session_project: dict[str, uuid.UUID] = {}
        self._session_model: dict[str, ModelConfig] = {}

    def create_session(self, project_id: uuid.UUID, model_config: ModelConfig | None = None) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        self._session_project[session_id] = project_id
        if model_config:
            self._session_model[session_id] = model_config
        return session_id

    def get_model(self, session_id: str) -> ModelConfig | None:
        return self._session_model.get(session_id)

    def get_session(self, session_id: str) -> list[dict] | None:
        return self._sessions.get(session_id)

    def get_messages(self, session_id: str) -> list[dict]:
        return self._sessions.get(session_id, [])

    def add_message(self, session_id: str, message: dict) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)

    def trim_history(self, session_id: str, max_messages: int = 40) -> None:
        """Trim conversation history, keeping the most recent messages."""
        messages = self._sessions.get(session_id, [])
        if len(messages) <= max_messages:
            return
        # Keep the last max_messages entries
        self._sessions[session_id] = messages[-max_messages:]

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._session_project.pop(session_id, None)
        self._session_model.pop(session_id, None)
