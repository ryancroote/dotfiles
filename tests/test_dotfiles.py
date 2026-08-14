import contextlib
import importlib.machinery
import importlib.util
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "dotfiles"
LOADER = importlib.machinery.SourceFileLoader("dotfiles_cli", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
dotfiles = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(dotfiles)


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.state = self.root / "state"
        (self.repo / "home").mkdir(parents=True)
        self.home.mkdir()
        self.deployment = dotfiles.Deployment(self.repo, self.home, self.state)

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

        with self.assertRaises(dotfiles.DotfilesError):
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
            dotfiles.remove_path(target)
            raise RuntimeError("simulated interruption")

        with mock.patch.object(dotfiles, "deploy_leaf", side_effect=fail_deploy):
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

    def test_unknown_restore_target_does_not_change_active_state(self):
        self.source(".profile", "managed\n")
        destination = self.target(".profile", "original\n")
        self.quiet_apply()

        with self.assertRaises(dotfiles.DotfilesError):
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


class PlatformTest(unittest.TestCase):
    def test_os_release_parser(self):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "os-release"
            release.write_text('ID="ubuntu"\nID_LIKE=debian\nPRETTY_NAME="Ubuntu Test"\n', encoding="utf-8")
            self.assertEqual(dotfiles.parse_os_release(release)["PRETTY_NAME"], "Ubuntu Test")

    def test_platform_families(self):
        self.assertEqual(dotfiles.platform_family("Darwin", {}), "macos")
        self.assertEqual(dotfiles.platform_family("Linux", {"ID": "ubuntu"}), "debian")
        self.assertEqual(dotfiles.platform_family("Linux", {"ID": "fedora"}), "fedora")
        self.assertEqual(dotfiles.platform_family("Linux", {"ID": "arch"}), "unsupported")

    def test_ubuntu_prerequisites(self):
        commands = dotfiles.prerequisite_commands("debian", True)
        self.assertEqual(commands[0], ["sudo", "apt-get", "update"])
        self.assertIn("build-essential", commands[1])
        self.assertIn("procps", commands[1])

    def test_fedora_prerequisites(self):
        commands = dotfiles.prerequisite_commands("fedora", True)
        self.assertIn("development-tools", commands[0])
        self.assertIn("procps-ng", commands[1])

    def test_existing_homebrew_skips_bootstrap_commands(self):
        brew = Path("/fake/bin/brew")
        with mock.patch.object(dotfiles, "find_brew", return_value=brew), mock.patch.object(
            dotfiles, "run_command"
        ) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                result = dotfiles.bootstrap_homebrew(assume_yes=True)
        self.assertEqual(result, brew)
        run.assert_not_called()

    def test_unsupported_linux_fails_with_instructions(self):
        with mock.patch.object(dotfiles, "find_brew", return_value=None), mock.patch.object(
            dotfiles, "platform_family", return_value="unsupported"
        ), mock.patch.object(
            dotfiles, "parse_os_release", return_value={"PRETTY_NAME": "Test Linux"}
        ), mock.patch.object(dotfiles.os, "geteuid", return_value=1000):
            with self.assertRaises(dotfiles.DotfilesError) as raised:
                dotfiles.bootstrap_homebrew(assume_yes=True)
        self.assertIn("Test Linux", str(raised.exception))

    def test_package_command_uses_repository_brewfile(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / "Brewfile").write_text('brew "git"\n', encoding="utf-8")
            with mock.patch.object(dotfiles, "find_brew", return_value=Path("/fake/brew")), mock.patch.object(
                dotfiles, "run_command"
            ) as run:
                dotfiles.install_packages(repo)
            run.assert_called_once_with(["/fake/brew", "bundle", f"--file={repo / 'Brewfile'}"])


if __name__ == "__main__":
    unittest.main()
