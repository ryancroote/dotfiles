"""Platform-safe Ghostty terminal installation."""

from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Mapping, Optional, Type

from .core import Console, DotfilesError
from .system import CommandRunner, PlatformDetector


class SnapSetupStrategy(ABC):
    """Builds commands that install Snap on one Linux platform family."""

    @abstractmethod
    def commands(
        self,
        assume_yes: bool,
        snap_mount_exists: bool,
    ) -> List[List[str]]:
        """Return native commands needed to make the snap command available."""


class DebianSnapSetupStrategy(SnapSetupStrategy):
    """Installs Snap through APT on Ubuntu and Debian-family systems."""

    def commands(
        self,
        assume_yes: bool,
        snap_mount_exists: bool,
    ) -> List[List[str]]:
        yes = ["-y"] if assume_yes else []
        return [
            ["sudo", "apt-get", "update"],
            ["sudo", "apt-get", "install", *yes, "snapd"],
        ]


class FedoraSnapSetupStrategy(SnapSetupStrategy):
    """Installs and activates Snap on Fedora-family systems."""

    def commands(
        self,
        assume_yes: bool,
        snap_mount_exists: bool,
    ) -> List[List[str]]:
        yes = ["-y"] if assume_yes else []
        commands = [
            ["sudo", "dnf", "install", *yes, "snapd"],
            ["sudo", "systemctl", "enable", "--now", "snapd.socket"],
        ]
        if not snap_mount_exists:
            commands.append(
                ["sudo", "ln", "-s", "/var/lib/snapd/snap", "/snap"]
            )
        return commands


class SnapSetupStrategyFactory:
    """Selects Snap setup commands for supported Linux platform families."""

    STRATEGIES: Mapping[str, Type[SnapSetupStrategy]] = {
        "debian": DebianSnapSetupStrategy,
        "fedora": FedoraSnapSetupStrategy,
    }

    def create(self, family: str) -> Optional[SnapSetupStrategy]:
        strategy_type = self.STRATEGIES.get(family)
        return strategy_type() if strategy_type else None


class GhosttyManager:
    """Ensures supported Linux systems have Snap and the Ghostty terminal."""

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        detector: Optional[PlatformDetector] = None,
        console: Optional[Console] = None,
        strategy_factory: Optional[SnapSetupStrategyFactory] = None,
    ) -> None:
        self.console = console or Console()
        self.runner = runner or CommandRunner(self.console)
        self.detector = detector or PlatformDetector()
        self.strategy_factory = strategy_factory or SnapSetupStrategyFactory()

    @staticmethod
    def _find_executable(name: str, candidates: List[Path]) -> Optional[Path]:
        found = shutil.which(name)
        paths = [Path(found)] if found else []
        paths.extend(candidates)
        for path in paths:
            if path.is_file() and os.access(str(path), os.X_OK):
                return path
        return None

    def find_snap(self) -> Optional[Path]:
        """Locate the Snap executable in standard Ubuntu and Fedora paths."""
        return self._find_executable("snap", [Path("/usr/bin/snap")])

    def find_ghostty(self) -> Optional[Path]:
        """Locate Ghostty, including the standard Snap wrapper paths."""
        return self._find_executable(
            "ghostty",
            [
                Path("/snap/bin/ghostty"),
                Path("/var/lib/snapd/snap/bin/ghostty"),
            ],
        )

    def install(self, assume_yes: bool = False, dry_run: bool = False) -> None:
        """Install Snap when absent, then install Ghostty on supported Linux."""
        ghostty = self.find_ghostty()
        if ghostty:
            self.console.print(f"Ghostty is already installed at {ghostty}")
            return

        family = self.detector.family()
        if family == "macos":
            return
        strategy = self.strategy_factory.create(family)
        if strategy is None:
            self.console.print(
                "Automatic Ghostty installation is only supported on Ubuntu/Debian "
                "and Fedora Linux"
            )
            return

        snap = self.find_snap()
        setup_commands = []
        if snap is None:
            snap_mount = Path("/snap")
            setup_commands = strategy.commands(
                assume_yes,
                snap_mount.exists() or snap_mount.is_symlink(),
            )

        self.console.print(f"Ghostty installation for {family} Linux:")
        for command in setup_commands:
            self.console.print(f"  {self.runner.printable(command)}")
        snap_command = str(snap) if snap else "snap"
        install_command = ["sudo", snap_command, "install", "ghostty", "--classic"]
        self.console.print(f"  {self.runner.printable(install_command)}")

        if dry_run:
            return

        prompt = (
            "Install Snap and Ghostty?"
            if setup_commands
            else "Install Ghostty from Snap?"
        )
        if not assume_yes and not self.console.confirm(prompt):
            raise DotfilesError("Ghostty installation cancelled")

        for command in setup_commands:
            self.runner.run(command)

        if snap is None:
            snap = self.find_snap()
            if snap is None:
                raise DotfilesError(
                    "Snap installation finished, but the snap executable could not be located"
                )
            install_command = [
                "sudo",
                str(snap),
                "install",
                "ghostty",
                "--classic",
            ]
        self.runner.run(install_command)
