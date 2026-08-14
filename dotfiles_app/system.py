"""Operating-system detection, command execution, and Homebrew management."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Type

from .core import BREW_INSTALL_URL, Console, DotfilesError


class CommandRunner:
    """Runs external commands without invoking a shell."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    @staticmethod
    def printable(command: Sequence[str]) -> str:
        return " ".join(shlex.quote(part) for part in command)

    def run(
        self,
        command: Sequence[str],
        env: Optional[Mapping[str, str]] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        self.console.print(f"+ {self.printable(command)}", flush=True)
        try:
            subprocess.run(
                list(command),
                check=True,
                env=dict(env) if env else None,
                cwd=str(cwd) if cwd else None,
            )
        except FileNotFoundError as error:
            raise DotfilesError(f"Required command was not found: {command[0]}") from error
        except subprocess.CalledProcessError as error:
            raise DotfilesError(
                f"Command failed with exit code {error.returncode}: "
                f"{self.printable(command)}"
            ) from error


class PrerequisiteStrategy(ABC):
    """Builds native package-manager commands for one platform family."""

    @abstractmethod
    def commands(self, assume_yes: bool) -> List[List[str]]:
        """Return commands needed before installing Homebrew."""


class DebianPrerequisiteStrategy(PrerequisiteStrategy):
    def commands(self, assume_yes: bool) -> List[List[str]]:
        yes = ["-y"] if assume_yes else []
        return [
            ["sudo", "apt-get", "update"],
            [
                "sudo",
                "apt-get",
                "install",
                *yes,
                "build-essential",
                "procps",
                "curl",
                "file",
                "git",
            ],
        ]


class FedoraPrerequisiteStrategy(PrerequisiteStrategy):
    def commands(self, assume_yes: bool) -> List[List[str]]:
        yes = ["-y"] if assume_yes else []
        return [
            ["sudo", "dnf", "group", "install", *yes, "development-tools"],
            [
                "sudo",
                "dnf",
                "install",
                *yes,
                "procps-ng",
                "curl",
                "file",
                "git",
            ],
        ]


class NoPrerequisiteStrategy(PrerequisiteStrategy):
    def commands(self, assume_yes: bool) -> List[List[str]]:
        return []


class PrerequisiteStrategyFactory:
    """Selects a prerequisite strategy by platform family."""

    STRATEGIES: Mapping[str, Type[PrerequisiteStrategy]] = {
        "debian": DebianPrerequisiteStrategy,
        "fedora": FedoraPrerequisiteStrategy,
    }

    def create(self, family: str) -> PrerequisiteStrategy:
        return self.STRATEGIES.get(family, NoPrerequisiteStrategy)()


class PlatformDetector:
    """Detects supported operating-system families and prerequisite strategies."""

    def __init__(
        self,
        strategy_factory: Optional[PrerequisiteStrategyFactory] = None,
    ) -> None:
        self.strategy_factory = strategy_factory or PrerequisiteStrategyFactory()

    def parse_os_release(self, path: Path = Path("/etc/os-release")) -> Dict[str, str]:
        values: Dict[str, str] = {}
        if not path.exists():
            return values
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
        return values

    def family(
        self,
        system: Optional[str] = None,
        release: Optional[Mapping[str, str]] = None,
    ) -> str:
        system = system or platform.system()
        if system == "Darwin":
            return "macos"
        if system != "Linux":
            return "unsupported"
        release_data = dict(release) if release is not None else self.parse_os_release()
        identifiers = {release_data.get("ID", "").lower()}
        identifiers.update(release_data.get("ID_LIKE", "").lower().split())
        if identifiers.intersection({"ubuntu", "debian", "linuxmint", "pop"}):
            return "debian"
        if identifiers.intersection({"fedora", "rhel", "centos"}):
            return "fedora"
        return "unsupported"

    def prerequisites(self, family: str) -> PrerequisiteStrategy:
        return self.strategy_factory.create(family)


class HomebrewManager:
    """Bootstraps Homebrew and applies the repository Brewfile."""

    def __init__(
        self,
        repo: Path,
        runner: Optional[CommandRunner] = None,
        detector: Optional[PlatformDetector] = None,
        console: Optional[Console] = None,
    ) -> None:
        self.repo = repo.resolve()
        self.console = console or Console()
        self.runner = runner or CommandRunner(self.console)
        self.detector = detector or PlatformDetector()

    def find_brew(self) -> Optional[Path]:
        found = shutil.which("brew")
        candidates = [
            Path(found) if found else None,
            Path("/opt/homebrew/bin/brew"),
            Path("/usr/local/bin/brew"),
            Path("/home/linuxbrew/.linuxbrew/bin/brew"),
            Path.home() / ".linuxbrew/bin/brew",
        ]
        for candidate in candidates:
            if candidate and candidate.is_file() and os.access(str(candidate), os.X_OK):
                return candidate
        return None

    def bootstrap(self, assume_yes: bool = False, dry_run: bool = False) -> Path:
        existing = self.find_brew()
        if existing:
            self.console.print(f"Homebrew is already installed at {existing}")
            return existing
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise DotfilesError("Homebrew must not be installed as root")
        family = self.detector.family()
        if family == "unsupported":
            release = self.detector.parse_os_release()
            name = release.get("PRETTY_NAME", platform.system())
            raise DotfilesError(
                f"Automatic Homebrew prerequisites are not supported on {name}. "
                "Install curl, file, git, procps, and compiler development tools, then retry."
            )
        commands = self.detector.prerequisites(family).commands(assume_yes)
        if commands:
            self.console.print(f"Homebrew prerequisites for {family} Linux:")
            for command in commands:
                self.console.print(f"  {self.runner.printable(command)}")
            if not dry_run:
                if not assume_yes and not self.console.confirm(
                    "Install native Homebrew prerequisites?"
                ):
                    raise DotfilesError("Bootstrap cancelled")
                for command in commands:
                    self.runner.run(command)
        if dry_run:
            self.console.print(
                f"Would download and run the official installer from {BREW_INSTALL_URL}"
            )
            return Path("brew")
        self.console.print(
            f"Downloading the official Homebrew installer from {BREW_INSTALL_URL}"
        )
        installer_path = self._download_installer()
        try:
            environment = os.environ.copy()
            if assume_yes:
                environment["NONINTERACTIVE"] = "1"
            self.runner.run(["/bin/bash", str(installer_path)], env=environment)
        finally:
            installer_path.unlink(missing_ok=True)
        brew = self.find_brew()
        if not brew:
            raise DotfilesError(
                "Homebrew installer finished, but the brew executable could not be located"
            )
        self.console.print(f"Homebrew installed at {brew}")
        return brew

    @staticmethod
    def _download_installer() -> Path:
        try:
            with urllib.request.urlopen(BREW_INSTALL_URL, timeout=30) as response:
                installer = response.read()
        except Exception as error:
            raise DotfilesError(
                f"Could not download the Homebrew installer: {error}"
            ) from error
        with tempfile.NamedTemporaryFile(
            prefix="homebrew-install-",
            suffix=".sh",
            delete=False,
        ) as handle:
            handle.write(installer)
            return Path(handle.name)

    def install_packages(self, dry_run: bool = False) -> None:
        brewfile = self.repo / "Brewfile"
        if not brewfile.is_file():
            raise DotfilesError(f"Brewfile does not exist: {brewfile}")
        brew = self.find_brew()
        if not brew:
            raise DotfilesError(
                "Homebrew is not installed; run './dotfiles bootstrap' first"
            )
        command = [str(brew), "bundle", f"--file={brewfile}"]
        if dry_run:
            self.console.print(f"Would run: {self.runner.printable(command)}")
        else:
            self.runner.run(command)
