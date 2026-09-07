import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import git
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AnalysisError
from app.models.project import Project, ProjectStatus

logger = logging.getLogger(__name__)


class GitManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _workspace_path(self, project_name: str) -> Path:
        return Path(settings.WORKSPACE_DIR) / project_name

    async def get_repository(self, project_name: str) -> git.Repo:
        workspace = self._workspace_path(project_name)
        if not workspace.exists() or not (workspace / ".git").exists():
            raise AnalysisError(f"Repository not found at {workspace}")
        try:
            return git.Repo(str(workspace))
        except git.GitError as e:
            raise AnalysisError(f"Invalid repository: {e}") from e

    async def resolve_commit(self, project_name: str, ref: str) -> git.Commit:
        if not ref or len(ref) > 255:
            raise AnalysisError("Invalid commit reference")
        repo = await self.get_repository(project_name)
        try:
            obj = repo.commit(ref)
        except (git.BadName, git.BadObject, ValueError) as e:
            raise AnalysisError(f"Commit not found: {ref}") from e
        return obj

    @staticmethod
    def commit_info(commit: git.Commit) -> dict:
        return {"sha": commit.hexsha, "short_sha": commit.hexsha[:7], "message": commit.message.strip(), "author": commit.author.name or commit.author.email or "unknown", "authored_at": datetime.fromtimestamp(commit.authored_date, tz=timezone.utc)}

    async def list_commits(self, project_name: str, limit: int = 50, ref: str | None = None) -> list[dict]:
        repo = await self.get_repository(project_name)
        try:
            commits = list(repo.iter_commits(ref or "HEAD", max_count=limit))
        except (git.BadName, git.GitCommandError) as e:
            raise AnalysisError(f"Commit reference not found: {ref}") from e
        return [self.commit_info(commit) for commit in commits]

    async def get_commit_info(self, project_name: str, commit_sha: str) -> dict:
        return self.commit_info(await self.resolve_commit(project_name, commit_sha))

    @staticmethod
    def validate_history_path(path: str) -> str:
        candidate = Path(path)
        if not path or candidate.is_absolute() or ".git" in candidate.parts or ".." in candidate.parts:
            raise AnalysisError("Invalid repository path")
        return path.replace("\\", "/").lstrip("./")

    async def get_commit_file_content(self, project_name: str, commit_sha: str, path: str) -> bytes:
        path = self.validate_history_path(path)
        commit = await self.resolve_commit(project_name, commit_sha)
        try:
            return (commit.tree / path).data_stream.read()
        except (KeyError, ValueError, AttributeError) as e:
            raise AnalysisError(f"File not found in commit: {path}") from e

    async def clone(self, project: Project) -> Path:
        workspace = self._workspace_path(project.name)
        if workspace.exists():
            logger.info(f"Repository already exists at {workspace}, pulling latest")
            try:
                repo = git.Repo(str(workspace))
                if repo.remotes:
                    repo.remotes.origin.pull(project.branch)
                project.commit = repo.head.commit.hexsha
            except Exception as e:
                logger.warning(f"Pull failed, using existing checkout: {e}")
                try:
                    project.commit = git.Repo(str(workspace)).head.commit.hexsha
                except Exception:
                    pass
        else:
            logger.info(f"Cloning {project.git_url} to {workspace}")
            project.status = ProjectStatus.CLONING
            await self.db.commit()
            try:
                git.Repo.clone_from(project.git_url, str(workspace), branch=project.branch)
                project.commit = git.Repo(str(workspace)).head.commit.hexsha
            except git.GitCommandError as e:
                project.status = ProjectStatus.ERROR
                await self.db.commit()
                raise AnalysisError(f"Failed to clone repository: {e}")
        await self.db.commit()
        return workspace

    async def get_file_list(self, project_name: str) -> list[str]:
        workspace = self._workspace_path(project_name)
        if not workspace.exists():
            raise AnalysisError(f"Repository not found at {workspace}")
        test_dir_parts = set(settings.TEST_DIR_PARTS)
        test_prefixes = tuple(settings.TEST_FILE_PREFIXES)
        test_suffixes = tuple(settings.TEST_FILE_SUFFIXES)
        java_files = []
        for root, dirs, files in os.walk(str(workspace)):
            if ".git" in root:
                continue
            rel_root = os.path.relpath(root, str(workspace)).replace(os.sep, "/")
            dirs[:] = [d for d in dirs if d not in test_dir_parts and not (rel_root == "src" and d == "test")]
            if any(part in rel_root.split("/") for part in test_dir_parts) or "src/test" in rel_root:
                continue
            for f in files:
                if f.endswith(".java") and not any(f.startswith(p) for p in test_prefixes) and not any(f.endswith(s) for s in test_suffixes):
                    java_files.append(os.path.relpath(os.path.join(root, f), str(workspace)).replace(os.sep, "/"))
        return sorted(java_files)

    async def read_file(self, project_name: str, file_path: str) -> str:
        workspace = self._workspace_path(project_name).resolve()
        full_path = (workspace / file_path).resolve()
        if not full_path.is_relative_to(workspace):
            raise AnalysisError("Path traversal detected")
        if not full_path.exists():
            raise AnalysisError(f"File not found: {full_path}")
        return full_path.read_text(encoding="utf-8", errors="replace")
