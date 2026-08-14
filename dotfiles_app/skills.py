"""Repository-managed Agent Skills integration."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional, Sequence

from .core import DotfilesError
from .system import CommandRunner


class SkillManager:
    """Runs npx skills while keeping installations in the canonical home tree."""

    ALIASES = {"a": "add", "rm": "remove", "upgrade": "update"}
    REPOSITORY_ONLY_COMMANDS = {"add", "remove", "update"}
    FORBIDDEN_FLAGS = {"-g", "--global", "-a", "--agent", "--all"}

    def __init__(self, repo: Path, runner: Optional[CommandRunner] = None) -> None:
        self.repo = repo.resolve()
        self.home_source = self.repo / "home"
        self.runner = runner or CommandRunner()

    def build_command(self, npx: Path, arguments: Sequence[str]) -> List[str]:
        prefix = [str(npx), "--yes", "skills"]
        if not arguments:
            return [*prefix, "--help"]
        command_name = self.ALIASES.get(arguments[0], arguments[0])
        command_arguments = list(arguments[1:])
        self._validate_arguments(command_name, command_arguments)
        command = [*prefix, command_name, *command_arguments]
        if command_name == "add":
            command.extend(["--agent", "universal"])
            if "--copy" not in command_arguments:
                command.append("--copy")
        elif command_name == "remove":
            command.extend(["--agent", "universal"])
        elif (
            command_name == "update"
            and "--project" not in command_arguments
            and "-p" not in command_arguments
        ):
            command.append("--project")
        return command

    def run(self, arguments: Sequence[str]) -> None:
        npx = shutil.which("npx")
        if not npx:
            raise DotfilesError(
                "npx is required; install packages with './dotfiles packages'"
            )
        if not self.home_source.is_dir():
            raise DotfilesError(
                f"Dotfile source directory does not exist: {self.home_source}"
            )
        self.runner.run(
            self.build_command(Path(npx), arguments),
            cwd=self.home_source,
        )

    def _validate_arguments(
        self,
        command_name: str,
        arguments: Sequence[str],
    ) -> None:
        if command_name not in self.REPOSITORY_ONLY_COMMANDS:
            return
        invalid = next(
            (
                argument
                for argument in arguments
                if argument in self.FORBIDDEN_FLAGS
                or argument.startswith("--global=")
                or argument.startswith("--agent=")
            ),
            None,
        )
        if invalid:
            raise DotfilesError(
                f"'{invalid}' is not allowed for repository-managed skills; "
                "skills must remain under home/.agents/skills"
            )
