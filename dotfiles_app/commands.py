"""Command pattern implementation for CLI operations."""

from __future__ import annotations

import argparse
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Type

from .configuration import ApplicationPaths
from .core import Console, DotfilesError
from .deployment import Deployment
from .skills import SkillManager
from .system import HomebrewManager, PlatformDetector


class DeploymentFactory:
    """Creates deployment aggregates for a command context."""

    def create(self, paths: ApplicationPaths, console: Console) -> Deployment:
        return Deployment(
            paths.repo,
            paths.target_home,
            paths.state_dir,
            console=console,
        )


@dataclass
class CommandContext:
    """Shared services available to commands."""

    paths: ApplicationPaths
    console: Console
    homebrew: HomebrewManager
    skills: SkillManager
    detector: PlatformDetector
    deployment_factory: DeploymentFactory = field(default_factory=DeploymentFactory)
    _deployment: Optional[Deployment] = field(default=None, init=False, repr=False)

    @property
    def deployment(self) -> Deployment:
        if self._deployment is None:
            self._deployment = self.deployment_factory.create(self.paths, self.console)
        return self._deployment


class CliCommand(ABC):
    """An executable CLI request."""

    def __init__(self, context: CommandContext, arguments: argparse.Namespace) -> None:
        self.context = context
        self.arguments = arguments

    @abstractmethod
    def execute(self) -> int:
        """Execute the request and return a process exit code."""


class BootstrapCommand(CliCommand):
    def execute(self) -> int:
        self.context.homebrew.bootstrap(
            self.arguments.yes,
            self.arguments.dry_run,
        )
        return 0


class PackagesCommand(CliCommand):
    def execute(self) -> int:
        self.context.homebrew.install_packages(self.arguments.dry_run)
        return 0


class ApplyCommand(CliCommand):
    def execute(self) -> int:
        self.context.deployment.apply(
            self.arguments.dry_run,
            self.arguments.yes,
        )
        return 0


class InstallCommand(CliCommand):
    def execute(self) -> int:
        self.context.homebrew.bootstrap(
            self.arguments.yes,
            self.arguments.dry_run,
        )
        if self.arguments.dry_run:
            self.context.console.print(
                f"Would install packages from {self.context.paths.repo / 'Brewfile'}"
            )
        else:
            self.context.homebrew.install_packages()
        self.context.deployment.apply(
            self.arguments.dry_run,
            self.arguments.yes,
        )
        return 0


class StatusCommand(CliCommand):
    def execute(self) -> int:
        return self.context.deployment.status()


class HistoryCommand(CliCommand):
    def execute(self) -> int:
        self.context.deployment.history()
        return 0


class RestoreCommand(CliCommand):
    def execute(self) -> int:
        self.context.deployment.restore(
            self.arguments.transaction,
            self.arguments.recover,
            self.arguments.force,
            self.arguments.yes,
        )
        return 0


class SkillsCommand(CliCommand):
    def execute(self) -> int:
        self.context.skills.run(self.arguments.arguments)
        return 0


class DoctorCommand(CliCommand):
    def execute(self) -> int:
        deployment = self.context.deployment
        problems = []
        family = self.context.detector.family()
        self.context.console.print(f"Platform:       {platform.system()} ({family})")
        self.context.console.print(f"Repository:     {self.context.paths.repo}")
        self.context.console.print(f"Source:         {deployment.source}")
        self.context.console.print(f"Target home:    {deployment.target_home}")
        self.context.console.print(f"State:          {deployment.state_dir}")
        brew = self.context.homebrew.find_brew()
        self.context.console.print(f"Homebrew:       {brew if brew else 'not installed'}")
        if not deployment.source.is_dir():
            problems.append("home/ source directory is missing")
        if deployment.journal_path.exists():
            problems.append("an interrupted transaction requires recovery")
        try:
            deployment.inventory()
        except DotfilesError as error:
            problems.append(str(error))
        if problems:
            for problem in problems:
                self.context.console.print(f"ERROR: {problem}", error=True)
            return 1
        self.context.console.print("Doctor found no dotfile deployment problems")
        return 0


class CommandFactory:
    """Maps parsed command names to concrete command objects."""

    DEFAULT_COMMANDS: Mapping[str, Type[CliCommand]] = {
        "bootstrap": BootstrapCommand,
        "packages": PackagesCommand,
        "apply": ApplyCommand,
        "install": InstallCommand,
        "status": StatusCommand,
        "history": HistoryCommand,
        "restore": RestoreCommand,
        "doctor": DoctorCommand,
        "skills": SkillsCommand,
    }

    def __init__(
        self,
        commands: Optional[Mapping[str, Type[CliCommand]]] = None,
    ) -> None:
        self._commands: Dict[str, Type[CliCommand]] = dict(
            self.DEFAULT_COMMANDS if commands is None else commands
        )

    def create(
        self,
        command_name: str,
        context: CommandContext,
        arguments: argparse.Namespace,
    ) -> CliCommand:
        command_type = self._commands.get(command_name)
        if command_type is None:
            raise DotfilesError(f"Unknown command: {command_name}")
        return command_type(context, arguments)
