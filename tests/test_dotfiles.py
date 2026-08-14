import contextlib
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dotfiles_app.app import ArgumentParserFactory, DotfilesApplication
from dotfiles_app.commands import ApplyCommand, CommandContext, CommandFactory
from dotfiles_app.core import DotfilesError
from dotfiles_app.deployment import Deployment
from dotfiles_app.skills import SkillManager
from dotfiles_app.system import CommandRunner, HomebrewManager, PlatformDetector


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.state = self.root / "state"
        (self.repo / "home").mkdir(parents=True)
        self.home.mkdir()
        self.deployment = Deployment(self.repo, self.home, self.state)

    def tearDown(self):
        self.temporary.cleanup()

    def source(self, relative, content="managed\n", mode=None):
        path = self.repo / "home" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if mode is not None:
            path.chmod(mode)
        return path

    def target(self, relative, content="existing\n"):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def quiet_apply(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.deployment.apply(assume_yes=True)

    def quiet_restore(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.deployment.restore(assume_yes=True, **kwargs)

    def test_conflicting_file_is_backed_up_and_restored(self):
        self.source(".config/tool/config", "new\n")
        destination = self.target(".config/tool/config", "old\n")

        transaction = self.quiet_apply()

        self.assertEqual(destination.read_text(encoding="utf-8"), "new\n")
        self.assertTrue((self.state / "transactions" / transaction / "backup").is_dir())
        self.quiet_restore()
        self.assertEqual(destination.read_text(encoding="utf-8"), "old\n")

    def test_apply_is_idempotent(self):
        self.source(".gitconfig")
        first = self.quiet_apply()
        second = self.quiet_apply()
        transactions = list((self.state / "transactions").iterdir())

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(transactions), 1)

    def test_removed_source_is_removed_and_can_be_restored(self):
        source = self.source(".config/app/config", "version one\n")
        destination = self.home / ".config/app/config"
        self.quiet_apply()
        source.unlink()

        self.quiet_apply()
        self.assertFalse(destination.exists())
        self.quiet_restore()
        self.assertEqual(destination.read_text(encoding="utf-8"), "version one\n")

    def test_file_mode_and_symlink_are_preserved(self):
        self.source("bin/tool", "#!/bin/sh\n", 0o755)
        link = self.repo / "home" / ".tool-link"
        os.symlink("bin/tool", link)

        self.quiet_apply()

        deployed = self.home / "bin/tool"
        self.assertEqual(stat.S_IMODE(deployed.stat().st_mode), 0o755)
        self.assertTrue((self.home / ".tool-link").is_symlink())
        self.assertEqual(os.readlink(self.home / ".tool-link"), "bin/tool")

    def test_restore_refuses_drift_and_force_rescues_it(self):
        self.source(".profile", "managed\n")
        destination = self.target(".profile", "original\n")
        self.quiet_apply()
        destination.write_text("local edit\n", encoding="utf-8")

        with self.assertRaises(DotfilesError):
            self.quiet_restore()
        self.quiet_restore(force=True)

        self.assertEqual(destination.read_text(encoding="utf-8"), "original\n")
        rescues = list((self.state / "rescues").iterdir())
        self.assertEqual(len(rescues), 1)

    def test_parent_symlink_conflict_is_reversible(self):
        external = self.root / "external-config"
        external.mkdir()
        os.symlink(str(external), self.home / ".config")
        self.source(".config/app/config")

        self.quiet_apply()
        self.assertFalse((self.home / ".config").is_symlink())
        self.assertTrue((self.home / ".config/app/config").is_file())
        self.quiet_restore()
        self.assertTrue((self.home / ".config").is_symlink())
        self.assertEqual(os.readlink(self.home / ".config"), str(external))

    def test_interrupted_apply_can_be_recovered(self):
        self.source(".profile", "managed\n")
        destination = self.target(".profile", "original\n")

        def fail_deploy(source, target):
            self.deployment.filesystem.remove(target)
            raise RuntimeError("simulated interruption")

        with mock.patch.object(
            self.deployment.filesystem,
            "deploy_leaf",
            side_effect=fail_deploy,
        ):
            with self.assertRaises(RuntimeError):
                self.quiet_apply()
        self.assertTrue((self.state / "journal.json").exists())

        self.quiet_restore(recover=True)
        self.assertEqual(destination.read_text(encoding="utf-8"), "original\n")
        self.assertFalse((self.state / "journal.json").exists())

    def test_status_reports_modified_file(self):
        self.source(".zshrc", "managed\n")
        destination = self.home / ".zshrc"
        self.quiet_apply()
        destination.write_text("changed\n", encoding="utf-8")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            result = self.deployment.status()

        self.assertEqual(result, 1)
        self.assertIn("modified  .zshrc", output.getvalue())

    def test_empty_source_directory_is_created_and_restored(self):
        source_directory = self.repo / "home" / ".agents"
        source_directory.mkdir()
        source_directory.chmod(0o750)
        self.quiet_apply()
        deployed = self.home / ".agents"
        self.assertTrue(deployed.is_dir())
        self.assertEqual(stat.S_IMODE(deployed.stat().st_mode), 0o750)
        self.quiet_restore()
        self.assertFalse(deployed.exists())

    def test_dry_run_does_not_create_state(self):
        self.source(".profile")
        with contextlib.redirect_stdout(io.StringIO()):
            self.deployment.apply(dry_run=True)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.home / ".profile").exists())

    def test_root_gitkeep_is_not_deployed(self):
        self.source(".gitkeep", "")
        self.quiet_apply()
        self.assertFalse((self.home / ".gitkeep").exists())

    def test_dotfilesignore_excludes_metadata_and_patterns(self):
        (self.repo / ".dotfilesignore").write_text(
            "# repository metadata\nskills-lock.json\n.config/cache/\n*.secret\n",
            encoding="utf-8",
        )
        self.source("skills-lock.json", "{}\n")
        self.source(".config/cache/generated", "ignored\n")
        self.source(".config/private.secret", "ignored\n")
        self.source(".config/app/config", "deployed\n")

        self.quiet_apply()

        self.assertFalse((self.home / "skills-lock.json").exists())
        self.assertFalse((self.home / ".config/cache").exists())
        self.assertFalse((self.home / ".config/private.secret").exists())
        self.assertEqual(
            (self.home / ".config/app/config").read_text(encoding="utf-8"),
            "deployed\n",
        )

    def test_unknown_restore_target_does_not_change_active_state(self):
        self.source(".profile", "managed\n")
        destination = self.target(".profile", "original\n")
        self.quiet_apply()

        with self.assertRaises(DotfilesError):
            self.quiet_restore(target="not-a-transaction")

        self.assertEqual(destination.read_text(encoding="utf-8"), "managed\n")

    def test_restore_specific_transaction_reverses_newer_transactions(self):
        source = self.source(".profile", "one\n")
        destination = self.target(".profile", "original\n")
        first = self.quiet_apply()
        source.write_text("two\n", encoding="utf-8")
        second = self.quiet_apply()
        source.write_text("three\n", encoding="utf-8")
        self.quiet_apply()

        self.quiet_restore(target=second)

        self.assertEqual(destination.read_text(encoding="utf-8"), "one\n")
        self.assertEqual(self.deployment.current_state()["transaction"], first)


class SkillManagementTest(unittest.TestCase):
    def setUp(self):
        self.runner = mock.Mock(spec=CommandRunner)
        self.manager = SkillManager(Path("/repo"), self.runner)

    def test_add_is_noninteractive_project_install_with_copies(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["add", "owner/repo", "--skill", "example"],
        )
        self.assertEqual(
            command,
            [
                "/fake/npx",
                "--yes",
                "skills",
                "add",
                "owner/repo",
                "--skill",
                "example",
                "--agent",
                "universal",
                "--copy",
                "--yes",
            ],
        )

    def test_add_does_not_duplicate_explicit_confirmation_flag(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["add", "owner/repo", "--yes"],
        )
        self.assertEqual(command.count("--yes"), 2)  # one for npx and one for skills

    def test_global_and_alternate_agent_flags_are_rejected(self):
        for flag in ("--global", "-g", "--agent", "-a", "--all"):
            with self.subTest(flag=flag), self.assertRaises(DotfilesError):
                self.manager.build_command(
                    Path("/fake/npx"),
                    ["add", "owner/repo", flag],
                )

    def test_remove_targets_the_whole_project_without_prompting(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["remove", "example"],
        )
        self.assertEqual(
            command,
            ["/fake/npx", "--yes", "skills", "remove", "example", "--yes"],
        )
        self.assertNotIn("--agent", command)

    def test_remove_all_is_allowed_for_the_project(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["remove", "--all"],
        )
        self.assertEqual(
            command,
            ["/fake/npx", "--yes", "skills", "remove", "--all", "--yes"],
        )

    def test_query_searches_the_skill_catalog(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["query", "python testing"],
        )
        self.assertEqual(
            command,
            ["/fake/npx", "--yes", "skills", "find", "python testing"],
        )

    def test_search_is_an_alias_for_query(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["search", "deployment"],
        )
        self.assertEqual(
            command,
            ["/fake/npx", "--yes", "skills", "find", "deployment"],
        )

    def test_update_is_limited_to_project(self):
        command = self.manager.build_command(
            Path("/fake/npx"),
            ["update", "--yes"],
        )
        self.assertEqual(
            command,
            ["/fake/npx", "--yes", "skills", "update", "--yes", "--project"],
        )

    def test_manager_runs_from_home_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "home").mkdir()
            manager = SkillManager(repo, self.runner)
            with mock.patch(
                "dotfiles_app.skills.shutil.which",
                return_value="/fake/npx",
            ):
                manager.run(["list", "--json"])
            self.runner.run.assert_called_once_with(
                ["/fake/npx", "--yes", "skills", "list", "--json"],
                cwd=repo.resolve() / "home",
            )

    def test_parser_passes_through_skill_arguments(self):
        arguments = ArgumentParserFactory.create().parse_args(
            ["skills", "add", "owner/repo", "--skill", "example"]
        )
        self.assertEqual(
            arguments.arguments,
            ["add", "owner/repo", "--skill", "example"],
        )


class CommandPatternTest(unittest.TestCase):
    def test_factory_creates_concrete_command(self):
        context = mock.Mock(spec=CommandContext)
        arguments = ArgumentParserFactory.create().parse_args(["apply", "--dry-run"])

        command = CommandFactory().create("apply", context, arguments)

        self.assertIsInstance(command, ApplyCommand)

    def test_application_delegates_to_command_object(self):
        command = mock.Mock()
        command.execute.return_value = 7
        factory = mock.Mock(spec=CommandFactory)
        factory.create.return_value = command

        with tempfile.TemporaryDirectory() as temporary:
            application = DotfilesApplication(
                repo=Path(temporary),
                command_factory=factory,
            )
            result = application.run(["status"])

        self.assertEqual(result, 7)
        command.execute.assert_called_once_with()
        factory.create.assert_called_once()


class PlatformTest(unittest.TestCase):
    def setUp(self):
        self.detector = PlatformDetector()

    def test_os_release_parser(self):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "os-release"
            release.write_text(
                'ID="ubuntu"\nID_LIKE=debian\nPRETTY_NAME="Ubuntu Test"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                self.detector.parse_os_release(release)["PRETTY_NAME"],
                "Ubuntu Test",
            )

    def test_platform_families(self):
        self.assertEqual(self.detector.family("Darwin", {}), "macos")
        self.assertEqual(self.detector.family("Linux", {"ID": "ubuntu"}), "debian")
        self.assertEqual(self.detector.family("Linux", {"ID": "fedora"}), "fedora")
        self.assertEqual(self.detector.family("Linux", {"ID": "arch"}), "unsupported")

    def test_ubuntu_prerequisites(self):
        commands = self.detector.prerequisites("debian").commands(True)
        self.assertEqual(commands[0], ["sudo", "apt-get", "update"])
        self.assertIn("build-essential", commands[1])
        self.assertIn("procps", commands[1])

    def test_fedora_prerequisites(self):
        commands = self.detector.prerequisites("fedora").commands(True)
        self.assertIn("development-tools", commands[0])
        self.assertIn("procps-ng", commands[1])


class HomebrewManagerTest(unittest.TestCase):
    def setUp(self):
        self.runner = mock.Mock(spec=CommandRunner)
        self.detector = mock.Mock(spec=PlatformDetector)
        self.manager = HomebrewManager(
            Path.cwd(),
            runner=self.runner,
            detector=self.detector,
        )

    def test_existing_homebrew_skips_bootstrap_commands(self):
        brew = Path("/fake/bin/brew")
        with mock.patch.object(self.manager, "find_brew", return_value=brew):
            with contextlib.redirect_stdout(io.StringIO()):
                result = self.manager.bootstrap(assume_yes=True)
        self.assertEqual(result, brew)
        self.runner.run.assert_not_called()

    def test_unsupported_linux_fails_with_instructions(self):
        self.detector.family.return_value = "unsupported"
        self.detector.parse_os_release.return_value = {"PRETTY_NAME": "Test Linux"}
        with mock.patch.object(self.manager, "find_brew", return_value=None), mock.patch(
            "dotfiles_app.system.os.geteuid",
            return_value=1000,
        ):
            with self.assertRaises(DotfilesError) as raised:
                self.manager.bootstrap(assume_yes=True)
        self.assertIn("Test Linux", str(raised.exception))

    def test_package_command_uses_repository_brewfile(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "Brewfile").write_text('brew "git"\n', encoding="utf-8")
            manager = HomebrewManager(repo, runner=self.runner, detector=self.detector)
            with mock.patch.object(
                manager,
                "find_brew",
                return_value=Path("/fake/brew"),
            ):
                manager.install_packages()
            self.runner.run.assert_called_once_with(
                ["/fake/brew", "bundle", f"--file={repo.resolve() / 'Brewfile'}"]
            )


if __name__ == "__main__":
    unittest.main()
