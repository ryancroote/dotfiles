"""Shared constants and small domain helpers."""

from __future__ import annotations

import datetime as dt
import sys
import uuid

VERSION = 1
BREW_INSTALL_URL = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"


class DotfilesError(RuntimeError):
    """A user-facing dotfiles operation error."""


class IdentifierFactory:
    """Creates timestamps and unique transaction identifiers."""

    @staticmethod
    def now() -> str:
        return dt.datetime.now(dt.timezone.utc).isoformat()

    @staticmethod
    def transaction_id() -> str:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{uuid.uuid4().hex[:8]}"


class Console:
    """Handles user-facing output and confirmation prompts."""

    def print(self, message: str = "", *, error: bool = False, flush: bool = False) -> None:
        print(message, file=sys.stderr if error else sys.stdout, flush=flush)

    def confirm(self, prompt: str) -> bool:
        if not sys.stdin.isatty():
            raise DotfilesError(
                f"Confirmation required for '{prompt}'; use --yes in non-interactive mode"
            )
        answer = input(f"{prompt} [y/N] ").strip().lower()
        return answer in ("y", "yes")
