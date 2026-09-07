import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AnalysisError
from app.models.project import Project
from app.schemas.comparison import ChangedFile, CommitDiffResult, DiffSummary, FileDiffResult, Hunk
from app.services.analyzer.git_manager import GitManager


class GitDiffService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.git = GitManager(db)

    async def _project_repo(self, project_id):
        project = await self.db.get(Project, project_id)
        if not project:
            raise AnalysisError("Project not found")
        return project, await self.git.get_repository(project.name)

    async def list_commits(self, project_id, limit=50, ref=None):
        project, _ = await self._project_repo(project_id)
        return await self.git.list_commits(project.name, min(limit, settings.COMPARISON_MAX_COMMITS), ref)

    @staticmethod
    def _change_type(item):
        return {"A": "added", "D": "deleted", "M": "modified", "R": "renamed", "C": "copied"}.get(item.change_type, "modified")

    @staticmethod
    def _path_allowed(path, pattern):
        if not pattern:
            return True
        return Path(path or "").match(pattern) or pattern.lower() in (path or "").lower()

    async def compare_commits(self, project_id, base_ref, head_ref, file_pattern=None):
        project, repo = await self._project_repo(project_id)
        base = await self.git.resolve_commit(project.name, base_ref)
        head = await self.git.resolve_commit(project.name, head_ref)
        if base.hexsha == head.hexsha:
            return CommitDiffResult(base_commit=self.git.commit_info(base), head_commit=self.git.commit_info(head), summary=DiffSummary(), files=[])
        diffs = base.diff(head, create_patch=False)
        files = []
        for item in diffs[: settings.COMPARISON_MAX_FILES]:
            path = item.b_path or item.a_path
            if not self._path_allowed(path, file_pattern):
                continue
            files.append(ChangedFile(old_path=item.a_path, new_path=item.b_path, change_type=self._change_type(item), additions=item.diff.count(b"\n") if item.diff else 0, deletions=0, is_binary=item.diff == b"" and item.change_type == "M"))
        summary = DiffSummary(files_changed=len(files))
        for f in files:
            setattr(summary, {"added": "added_files", "deleted": "deleted_files", "modified": "modified_files", "renamed": "renamed_files", "copied": "copied_files"}[f.change_type], getattr(summary, {"added": "added_files", "deleted": "deleted_files", "modified": "modified_files", "renamed": "renamed_files", "copied": "copied_files"}[f.change_type]) + 1)
            summary.additions += f.additions
            summary.deletions += f.deletions
        return CommitDiffResult(base_commit=self.git.commit_info(base), head_commit=self.git.commit_info(head), summary=summary, files=files)

    async def get_file_diff(self, project_id, base_ref, head_ref, path):
        project, repo = await self._project_repo(project_id)
        path = self.git.validate_history_path(path)
        base = await self.git.resolve_commit(project.name, base_ref)
        head = await self.git.resolve_commit(project.name, head_ref)
        items = [d for d in base.diff(head, paths=path, create_patch=True)]
        if not items:
            raise AnalysisError(f"File not changed: {path}")
        item = items[0]
        patch_bytes = item.diff or b""
        is_binary = b"\x00" in patch_bytes
        patch = None if is_binary else patch_bytes[:settings.COMPARISON_MAX_PATCH_BYTES].decode("utf-8", "replace")
        truncated = len(patch_bytes) > settings.COMPARISON_MAX_PATCH_BYTES
        old_content = new_content = None
        if not is_binary:
            for commit, attr in ((base, "old_content"), (head, "new_content")):
                try:
                    data = await self.git.get_commit_file_content(project.name, commit.hexsha, path)
                    value = data[:settings.COMPARISON_MAX_FILE_BYTES].decode("utf-8", "replace")
                    if attr == "old_content": old_content = value
                    else: new_content = value
                    truncated = truncated or len(data) > settings.COMPARISON_MAX_FILE_BYTES
                except AnalysisError:
                    pass
        hunks = []
        if patch:
            for match in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$", patch, re.M):
                lines = patch[match.end():].splitlines()
                next_hunk = next((m.start() for m in re.finditer(r"^@@ ", patch[match.end():], re.M)), len(patch) - match.end())
                hunks.append(Hunk(old_start=int(match.group(1)), old_count=int(match.group(2) or 1), new_start=int(match.group(3)), new_count=int(match.group(4) or 1), lines=lines[:next_hunk]))
        return FileDiffResult(old_path=item.a_path, new_path=item.b_path, change_type=self._change_type(item), additions=0, deletions=0, is_binary=is_binary, is_truncated=truncated, old_content=old_content, new_content=new_content, patch=patch, hunks=hunks)


async def get_git_diff_service(db: AsyncSession) -> GitDiffService:
    return GitDiffService(db)
