import os
import logging
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
                repo = git.Repo.clone_from(
                    project.git_url,
                    str(workspace),
                    branch=project.branch,
                )
                project.commit = repo.head.commit.hexsha
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
            # Prune test directories (modifying dirs in-place prevents os.walk from descending)
            dirs[:] = [
                d for d in dirs
                if d not in test_dir_parts and not (rel_root == "src" and d == "test")
            ]
            # Skip if already inside a test directory
            if any(part in rel_root.split("/") for part in test_dir_parts) or "src/test" in rel_root:
                continue
            for f in files:
                if not f.endswith(".java"):
                    continue
                if any(f.startswith(p) for p in test_prefixes):
                    continue
                if any(f.endswith(s) for s in test_suffixes):
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, str(workspace))
                java_files.append(rel.replace(os.sep, "/"))
        return sorted(java_files)

    async def read_file(self, project_name: str, file_path: str) -> str:
        workspace = self._workspace_path(project_name).resolve()
        full_path = (workspace / file_path).resolve()
        if not full_path.is_relative_to(workspace):
            raise AnalysisError("Path traversal detected")
        if not full_path.exists():
            raise AnalysisError(f"File not found: {full_path}")
        return full_path.read_text(encoding="utf-8", errors="replace")
