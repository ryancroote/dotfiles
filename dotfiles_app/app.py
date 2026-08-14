"""Command-line application composition and dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .commands import CommandContext, CommandFactory
from .configuration import ApplicationPaths
from .core import Console, DotfilesError
from .skills import SkillManager
from .system import CommandRunner, HomebrewManager, PlatformDetector


class ArgumentParserFactory:
    """Builds the public command-line interface."""

    @staticmethod
    def create() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Transactional dotfile deployment and Homebrew bootstrap utility."
        )
        parser.add_argument(
            "--target-home",
            help="deploy into this home instead of $HOME",
        )
        parser.add_argument(
            "--state-dir",
            help="override the transaction state directory",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        install = subparsers.add_parser(
            "install",
            help="bootstrap, install packages, and deploy dotfiles",
        )
        ArgumentParserFactory._action_flags(install)
        bootstrap = subparsers.add_parser(
            "bootstrap",
            help="install Homebrew and its prerequisites",
        )
        ArgumentParserFactory._action_flags(bootstrap)
        packages = subparsers.add_parser(
            "packages",
            help="install the repository Brewfile",
        )
        ArgumentParserFactory._action_flags(packages, yes=False)
        apply = subparsers.add_parser(
            "apply",
            help="transactionally deploy home/",
        )
        ArgumentParserFactory._action_flags(apply)
        subparsers.add_parser("status", help="show active-home drift")
        subparsers.add_parser("history", help="list deployment transactions")
        restore = subparsers.add_parser(
            "restore",
            help="restore state from a transaction",
        )
        restore.add_argument(
            "transaction",
            nargs="?",
            default="latest",
            help="latest or an active transaction ID",
        )
        restore.add_argument(
            "--recover",
            action="store_true",
            help="recover an interrupted apply",
        )
        restore.add_argument(
            "--force",
            action="store_true",
            help="rescue drift and restore anyway",
        )
        restore.add_argument("-y", "--yes", action="store_true", help="do not prompt")
        subparsers.add_parser("doctor", help="check platform and deployment health")
        skills = subparsers.add_parser(
            "skills",
            help="manage repository agent skills with npx",
        )
        skills.add_argument(
            "arguments",
            nargs=argparse.REMAINDER,
            help="arguments passed to npx skills",
        )
        return parser

    @staticmethod
    def _action_flags(
        command: argparse.ArgumentParser,
        yes: bool = True,
        dry: bool = True,
    ) -> None:
        if yes:
            command.add_argument("-y", "--yes", action="store_true", help="do not prompt")
        if dry:
            command.add_argument(
                "--dry-run",
                action="store_true",
                help="show actions without changing anything",
            )


class DotfilesApplication:
    """Composes services and delegates execution to command objects."""

    def __init__(
        self,
        repo: Optional[Path] = None,
        console: Optional[Console] = None,
        runner: Optional[CommandRunner] = None,
        detector: Optional[PlatformDetector] = None,
        command_factory: Optional[CommandFactory] = None,
    ) -> None:
        self.repo = (repo or Path(__file__).resolve().parents[1]).resolve()
        self.console = console or Console()
        self.runner = runner or CommandRunner(self.console)
        self.detector = detector or PlatformDetector()
        self.homebrew = HomebrewManager(
            self.repo,
            self.runner,
            self.detector,
            self.console,
        )
        self.skills = SkillManager(self.repo, self.runner)
        self.command_factory = command_factory or CommandFactory()
        self.parser = ArgumentParserFactory.create()

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        arguments = self.parser.parse_args(argv)
        paths = ApplicationPaths.from_arguments(self.repo, arguments)
        context = CommandContext(
            paths,
            self.console,
            self.homebrew,
            self.skills,
            self.detector,
        )
        try:
            command = self.command_factory.create(
                arguments.command,
                context,
                arguments,
            )
            return command.execute()
        except DotfilesError as error:
            self.console.print(f"error: {error}", error=True)
            return 2
        except KeyboardInterrupt:
            self.console.print("error: interrupted", error=True)
            return 130


def main(argv: Optional[Sequence[str]] = None) -> int:
    return DotfilesApplication().run(argv)


if __name__ == "__main__":
    sys.exit(main())
