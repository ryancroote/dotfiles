"""Application path configuration."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplicationPaths:
    """Resolved repository, target-home, and state paths."""

    repo: Path
    target_home: Path
    state_dir: Path

    @classmethod
    def from_arguments(cls, repo: Path, arguments: argparse.Namespace) -> "ApplicationPaths":
        target = (
            Path(arguments.target_home).expanduser()
            if arguments.target_home
            else Path.home()
        )
        state = (
            Path(arguments.state_dir).expanduser()
            if arguments.state_dir
            else cls.default_state_dir(target)
        )
        return cls(repo.resolve(), target, state)

    @staticmethod
    def default_state_dir(target_home: Path) -> Path:
        xdg = os.environ.get("XDG_STATE_HOME")
        if xdg and target_home.resolve() == Path.home().resolve():
            return Path(xdg).expanduser() / "dotfiles"
        return target_home / ".local/state/dotfiles"
