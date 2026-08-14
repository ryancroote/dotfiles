"""Transactional home-directory deployment."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set

from .core import Console, DotfilesError, IdentifierFactory, VERSION
from .filesystem import FileSystem, JsonStore

Metadata = Dict[str, Any]
State = Dict[str, Any]


@dataclass(frozen=True)
class SourceInventory:
    files: Dict[str, Metadata]
    directories: List[str]


@dataclass(frozen=True)
class DeploymentPlan:
    descriptions: List[str]
    desired: Dict[str, Metadata]
    required_directories: List[str]
    previous_state: State


class IgnoreRules:
    """Loads and evaluates repository deployment exclusions."""

    def __init__(self, patterns: Sequence[str] = ()) -> None:
        self.patterns = tuple(patterns)

    @classmethod
    def from_file(cls, path: Path) -> "IgnoreRules":
        if not path.exists():
            return cls()
        patterns: List[str] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            pattern = raw_line.strip()
            if pattern and not pattern.startswith("#"):
                patterns.append(pattern.strip("/"))
        return cls(patterns)

    def matches(self, relative: str) -> bool:
        parts = Path(relative).parts
        for pattern in self.patterns:
            if not pattern:
                continue
            candidates = [relative] if "/" in pattern else list(parts)
            if any(fnmatch.fnmatchcase(candidate, pattern) for candidate in candidates):
                return True
        return False


class SourceTree:
    """Builds a validated inventory from the canonical home tree."""

    def __init__(self, repo: Path, filesystem: FileSystem) -> None:
        self.repo = repo.resolve()
        self.root = (self.repo / "home").resolve()
        self.ignore_path = self.repo / ".dotfilesignore"
        self.filesystem = filesystem
        if not self.root.is_dir():
            raise DotfilesError(f"Dotfile source directory does not exist: {self.root}")

    def inventory(self, target_home: Path, state_dir: Path) -> SourceInventory:
        leaves: Dict[str, Metadata] = {}
        directories: List[str] = []
        rules = IgnoreRules.from_file(self.ignore_path)
        for root, dirnames, filenames in os.walk(str(self.root), followlinks=False):
            root_path = Path(root)
            for name in list(dirnames):
                child = root_path / name
                relative = child.relative_to(self.root).as_posix()
                if rules.matches(relative):
                    dirnames.remove(name)
                elif child.is_symlink():
                    dirnames.remove(name)
                    leaves[relative] = self.filesystem.metadata(child, recursive=False)
                else:
                    directories.append(relative)
            for name in filenames:
                child = root_path / name
                relative = child.relative_to(self.root).as_posix()
                if relative == ".gitkeep" or rules.matches(relative):
                    continue
                metadata = self.filesystem.metadata(child, recursive=False)
                if metadata["kind"] not in ("file", "symlink"):
                    raise DotfilesError(f"Unsupported source object: {child}")
                leaves[relative] = metadata
        self._validate_paths(leaves, directories, target_home, state_dir)
        ordered_directories = sorted(
            set(directories),
            key=lambda item: (item.count("/"), item),
        )
        return SourceInventory(dict(sorted(leaves.items())), ordered_directories)

    def _validate_paths(
        self,
        leaves: Mapping[str, Metadata],
        directories: Sequence[str],
        target_home: Path,
        state_dir: Path,
    ) -> None:
        for relative in leaves:
            destination = target_home / Path(relative)
            if self.filesystem.intersects(destination, state_dir):
                raise DotfilesError(f"Managed path would overlap installer state: {relative}")
            if self.filesystem.intersects(destination, self.repo):
                raise DotfilesError(f"Managed path would overlap this repository: {relative}")
        for relative in directories:
            destination = target_home / Path(relative)
            if self.filesystem.is_relative_to(destination, state_dir):
                raise DotfilesError(f"Managed directory would overlap installer state: {relative}")
            if self.filesystem.is_relative_to(destination, self.repo):
                raise DotfilesError(f"Managed directory would overlap this repository: {relative}")


class DeploymentStateStore:
    """Owns deployment state, journals, and transaction manifests."""

    @staticmethod
    def empty_state() -> State:
        return {
            "version": VERSION,
            "transaction": None,
            "files": {},
            "created_dirs": [],
        }

    def __init__(self, root: Path, json_store: JsonStore) -> None:
        self.root = root.expanduser().resolve()
        self.transactions_dir = self.root / "transactions"
        self.current_path = self.root / "current.json"
        self.journal_path = self.root / "journal.json"
        self.json = json_store

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass
        self.transactions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def current(self) -> State:
        state = self.json.read(self.current_path, self.empty_state())
        if state.get("version") != VERSION:
            raise DotfilesError("Unsupported deployment state version")
        state.setdefault("files", {})
        state.setdefault("created_dirs", [])
        return state

    def write_current(self, state: Mapping[str, Any]) -> None:
        self.json.write(self.current_path, state)

    def assert_no_interruption(self) -> None:
        if self.journal_path.exists():
            journal = self.json.read(self.journal_path)
            transaction = journal.get("transaction", "unknown")
            raise DotfilesError(
                f"An interrupted transaction ({transaction}) needs recovery. "
                "Run './dotfiles restore --recover'."
            )

    def transaction_dir(self, transaction: str) -> Path:
        return self.transactions_dir / transaction

    def manifest_path(self, transaction: str) -> Path:
        return self.transaction_dir(transaction) / "manifest.json"

    def read_manifest(self, transaction: str) -> State:
        return self.json.read(self.manifest_path(transaction))


class DeploymentTransaction:
    """Journals filesystem mutations before they occur."""

    def __init__(
        self,
        state_store: DeploymentStateStore,
        filesystem: FileSystem,
        target_home: Path,
        previous_state: State,
        identifiers: IdentifierFactory,
    ) -> None:
        self.state_store = state_store
        self.filesystem = filesystem
        self.target_home = target_home
        self.id = identifiers.transaction_id()
        self.directory = state_store.transaction_dir(self.id)
        self.directory.mkdir(parents=True, mode=0o700)
        self.manifest_path = state_store.manifest_path(self.id)
        self.manifest: State = {
            "version": VERSION,
            "id": self.id,
            "created_at": identifiers.now(),
            "status": "in_progress",
            "previous_state": previous_state,
            "actions": [],
        }
        state_store.json.write(self.manifest_path, self.manifest)
        state_store.json.write(
            state_store.journal_path,
            {"version": VERSION, "transaction": self.id},
        )
        self.identifiers = identifiers

    @property
    def actions(self) -> List[State]:
        return self.manifest["actions"]

    def mutate(self, relative: str, operation: str, callback: Callable[[Path], None]) -> None:
        target = self.target_home / Path(relative)
        before = self.filesystem.metadata(target)
        action_number = len(self.actions)
        backup_name: Optional[str] = None
        if before["kind"] != "absent":
            backup_name = f"{action_number:06d}"
            self.filesystem.copy(target, self.directory / "backup" / backup_name)
        action = {
            "path": relative,
            "operation": operation,
            "before": before,
            "backup": backup_name,
        }
        self.actions.append(action)
        self.state_store.json.write(self.manifest_path, self.manifest)
        callback(target)

    def complete(self, final_state: State) -> None:
        for action in self.actions:
            action["after"] = self.filesystem.metadata(
                self.target_home / Path(action["path"])
            )
        self.manifest["status"] = "complete"
        self.manifest["completed_at"] = self.identifiers.now()
        self.manifest["result_state"] = final_state
        self.state_store.write_current(final_state)
        self.state_store.json.write(self.manifest_path, self.manifest)
        self.state_store.journal_path.unlink()


class Deployment:
    """Coordinates planning, applying, and restoring dotfile transactions."""

    def __init__(
        self,
        repo: Path,
        target_home: Path,
        state_dir: Path,
        filesystem: Optional[FileSystem] = None,
        console: Optional[Console] = None,
        identifiers: Optional[IdentifierFactory] = None,
    ) -> None:
        self.repo = repo.resolve()
        self.target_home = target_home.expanduser().resolve()
        if self.target_home == Path("/"):
            raise DotfilesError("Refusing to use the filesystem root as the target home")
        self.filesystem = filesystem or FileSystem()
        self.console = console or Console()
        self.identifiers = identifiers or IdentifierFactory()
        self.source_tree = SourceTree(self.repo, self.filesystem)
        self.source = self.source_tree.root
        self.state = DeploymentStateStore(
            state_dir,
            JsonStore(self.filesystem),
        )

    @property
    def state_dir(self) -> Path:
        return self.state.root

    @property
    def transactions_dir(self) -> Path:
        return self.state.transactions_dir

    @property
    def current_path(self) -> Path:
        return self.state.current_path

    @property
    def journal_path(self) -> Path:
        return self.state.journal_path

    def inventory(self) -> SourceInventory:
        return self.source_tree.inventory(self.target_home, self.state.root)

    def current_state(self) -> State:
        return self.state.current()

    def status(self) -> int:
        desired = self.inventory().files
        managed = self.current_state().get("files", {})
        findings: List[str] = []
        for relative, source_metadata in desired.items():
            destination = self.target_home / Path(relative)
            actual = self.filesystem.metadata(destination, recursive=False)
            if relative not in managed and actual["kind"] != "absent":
                findings.append(f"conflict  {relative}")
            elif actual["kind"] == "absent":
                findings.append(f"missing   {relative}")
            elif not self.filesystem.same(actual, source_metadata):
                findings.append(f"modified  {relative}")
        for relative in sorted(set(managed) - set(desired)):
            if self.filesystem.exists(self.target_home / Path(relative)):
                findings.append(f"stale     {relative}")
        if findings:
            self.console.print("\n".join(findings))
            return 1
        self.console.print(f"Clean: {len(desired)} managed file(s)")
        return 0

    def plan(self) -> DeploymentPlan:
        inventory = self.inventory()
        desired = inventory.files
        current = self.current_state()
        managed = current.get("files", {})
        descriptions: List[str] = []
        required_directories = set(inventory.directories)
        for relative in desired:
            parent = Path(relative).parent
            while parent != Path("."):
                required_directories.add(parent.as_posix())
                parent = parent.parent
        ordered_directories = sorted(
            required_directories,
            key=lambda item: (item.count("/"), item),
        )
        for relative in ordered_directories:
            destination = self.target_home / Path(relative)
            if (
                not self.filesystem.exists(destination)
                or destination.is_symlink()
                or not destination.is_dir()
            ):
                descriptions.append(f"ensure directory {relative}")
        for relative, metadata in desired.items():
            actual = self.filesystem.metadata(
                self.target_home / Path(relative),
                recursive=False,
            )
            if not self.filesystem.same(actual, metadata):
                descriptions.append(f"deploy {relative}")
        desired_paths = [Path(item) for item in desired]
        for relative in sorted(set(managed) - set(desired)):
            old = Path(relative)
            covered = relative in required_directories or any(
                new != old and new in old.parents for new in desired_paths
            )
            if not covered and self.filesystem.exists(self.target_home / old):
                descriptions.append(f"remove {relative}")
        for relative in current.get("created_dirs", []):
            if relative not in required_directories:
                path = self.target_home / Path(relative)
                if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
                    descriptions.append(f"remove empty directory {relative}")
        return DeploymentPlan(descriptions, desired, ordered_directories, current)

    def apply(self, dry_run: bool = False, assume_yes: bool = False) -> Optional[str]:
        self.state.assert_no_interruption()
        plan = self.plan()
        if not plan.descriptions:
            if not dry_run:
                self.state.ensure()
                self.state.write_current(
                    {
                        "version": VERSION,
                        "transaction": plan.previous_state.get("transaction"),
                        "files": plan.desired,
                        "created_dirs": plan.previous_state.get("created_dirs", []),
                        "updated_at": self.identifiers.now(),
                    }
                )
            self.console.print("No dotfile changes to apply")
            return None
        self.console.print("Planned dotfile changes:")
        for description in plan.descriptions:
            self.console.print(f"  - {description}")
        if dry_run:
            return None
        if not assume_yes and not self.console.confirm("Apply these changes?"):
            raise DotfilesError("Apply cancelled")

        self.state.ensure()
        transaction = DeploymentTransaction(
            self.state,
            self.filesystem,
            self.target_home,
            plan.previous_state,
            self.identifiers,
        )
        created_directories = set(plan.previous_state.get("created_dirs", []))
        self._execute_plan(plan, transaction, created_directories)
        final_state = {
            "version": VERSION,
            "transaction": transaction.id,
            "files": plan.desired,
            "created_dirs": sorted(created_directories),
            "updated_at": self.identifiers.now(),
        }
        transaction.complete(final_state)
        self.console.print(f"Applied transaction {transaction.id}")
        return transaction.id

    def _execute_plan(
        self,
        plan: DeploymentPlan,
        transaction: DeploymentTransaction,
        created_directories: Set[str],
    ) -> None:
        required = set(plan.required_directories)
        for relative in plan.required_directories:
            destination = self.target_home / Path(relative)
            if (
                self.filesystem.exists(destination)
                and not destination.is_symlink()
                and destination.is_dir()
            ):
                continue
            source_directory = self.source / Path(relative)
            mode = self.filesystem.mode(source_directory) if source_directory.is_dir() else 0o700

            def create_directory(target: Path, directory_mode: int = mode) -> None:
                self.filesystem.remove(target)
                target.mkdir(parents=False, mode=directory_mode)
                target.chmod(directory_mode)

            transaction.mutate(relative, "ensure_directory", create_directory)
            created_directories.add(relative)

        desired_paths = [Path(item) for item in plan.desired]
        for relative, metadata in plan.desired.items():
            destination = self.target_home / Path(relative)
            if self.filesystem.same(
                self.filesystem.metadata(destination, recursive=False),
                metadata,
            ):
                continue
            source = self.source / Path(relative)
            transaction.mutate(
                relative,
                "deploy",
                lambda target, source_path=source: self.filesystem.deploy_leaf(
                    source_path, target
                ),
            )

        managed = plan.previous_state.get("files", {})
        removed = sorted(
            set(managed) - set(plan.desired),
            key=lambda item: (-item.count("/"), item),
        )
        for relative in removed:
            old = Path(relative)
            covered = relative in required or any(
                new != old and new in old.parents for new in desired_paths
            )
            if covered or not self.filesystem.exists(self.target_home / old):
                continue
            transaction.mutate(relative, "remove", self.filesystem.remove)

        for relative in sorted(
            list(created_directories),
            key=lambda item: (-item.count("/"), item),
        ):
            if relative in required:
                continue
            directory = self.target_home / Path(relative)
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                transaction.mutate(
                    relative,
                    "remove_empty_directory",
                    self.filesystem.remove,
                )
                created_directories.remove(relative)

    def history(self) -> List[State]:
        self.state.ensure()
        records = [
            self.state.json.read(path)
            for path in sorted(
                self.transactions_dir.glob("*/manifest.json"),
                reverse=True,
            )
        ]
        if not records:
            self.console.print("No deployment transactions")
            return records
        active = self.current_state().get("transaction")
        for record in records:
            marker = "*" if record.get("id") == active else " "
            self.console.print(
                f"{marker} {record.get('id', 'unknown')}  "
                f"{record.get('status', 'unknown'):11}  "
                f"{len(record.get('actions', []))} change(s)"
            )
        return records

    def restore(
        self,
        target: str = "latest",
        recover: bool = False,
        force: bool = False,
        assume_yes: bool = False,
    ) -> None:
        self.state.ensure()
        if recover:
            self._recover_interrupted(assume_yes)
            return
        self.state.assert_no_interruption()
        active = self.current_state().get("transaction")
        if not active:
            raise DotfilesError("There is no active transaction to restore")
        if target != "latest" and target not in self._active_chain(str(active)):
            raise DotfilesError(f"Transaction is not in the active history: {target}")
        while active:
            transaction = str(active)
            manifest = self.state.read_manifest(transaction)
            if manifest.get("status") != "complete":
                raise DotfilesError(f"Active transaction is not restorable: {transaction}")
            if not assume_yes and not self.console.confirm(
                f"Restore state before transaction {transaction}?"
            ):
                raise DotfilesError("Restore cancelled")
            self._reverse(manifest, recover=False, force=force)
            if target in ("latest", transaction):
                return
            active = self.current_state().get("transaction")
        raise DotfilesError(f"Transaction is not in the active history: {target}")

    def _recover_interrupted(self, assume_yes: bool) -> None:
        if not self.journal_path.exists():
            raise DotfilesError("There is no interrupted transaction to recover")
        transaction = str(self.state.json.read(self.journal_path).get("transaction"))
        manifest = self.state.read_manifest(transaction)
        if not assume_yes and not self.console.confirm(
            f"Recover interrupted transaction {transaction}?"
        ):
            raise DotfilesError("Recovery cancelled")
        self._reverse(manifest, recover=True, force=True)

    def _active_chain(self, active: str) -> List[str]:
        chain: List[str] = []
        cursor: Optional[str] = active
        while cursor:
            chain.append(cursor)
            manifest = self.state.read_manifest(cursor)
            previous = manifest.get("previous_state") or {}
            prior = previous.get("transaction")
            cursor = str(prior) if prior else None
        return chain

    def _reverse(self, manifest: State, recover: bool, force: bool) -> None:
        transaction = str(manifest.get("id", "unknown"))
        actions = manifest.get("actions", [])
        if not isinstance(actions, list):
            raise DotfilesError(f"Invalid transaction manifest: {transaction}")
        drift = self._drifted_actions(transaction, actions) if not recover else []
        if drift and not force:
            joined = ", ".join(drift[:5])
            suffix = "..." if len(drift) > 5 else ""
            raise DotfilesError(
                f"Active files changed after transaction {transaction}: {joined}{suffix}. "
                "Re-run with --force to preserve them in a rescue backup and restore anyway."
            )
        rescue = (
            self._rescue_actions(actions, "recovery" if recover else "restore")
            if force or recover
            else None
        )
        transaction_dir = self.state.transaction_dir(transaction)
        for action in reversed(actions):
            target = self.target_home / Path(action["path"])
            self.filesystem.remove(target)
            backup_name = action.get("backup")
            if backup_name:
                self.filesystem.copy(
                    transaction_dir / "backup" / str(backup_name),
                    target,
                )
        previous = manifest.get("previous_state") or self.state.empty_state()
        self.state.write_current(previous)
        manifest["status"] = "recovered" if recover else "rolled_back"
        manifest["restored_at"] = self.identifiers.now()
        if rescue:
            manifest["rescue"] = str(rescue)
        self.state.json.write(self.state.manifest_path(transaction), manifest)
        if self.journal_path.exists():
            self.journal_path.unlink()
        message = (
            f"Recovered interrupted transaction {transaction}"
            if recover
            else f"Restored state before {transaction}"
        )
        if rescue:
            message += f" (current files rescued to {rescue})"
        self.console.print(message)

    def _drifted_actions(self, transaction: str, actions: Sequence[State]) -> List[str]:
        drift: List[str] = []
        for action in actions:
            expected = action.get("after")
            if expected is None:
                raise DotfilesError(
                    f"Transaction {transaction} has no completed after-state"
                )
            actual = self.filesystem.metadata(
                self.target_home / Path(action["path"])
            )
            if not self.filesystem.same(actual, expected):
                drift.append(str(action["path"]))
        return drift

    def _rescue_actions(
        self,
        actions: Sequence[Mapping[str, Any]],
        label: str,
    ) -> Optional[Path]:
        paths = [Path(str(action["path"])) for action in actions]
        topmost = [
            path for path in paths if not any(parent in paths for parent in path.parents)
        ]
        existing = [
            path for path in topmost if self.filesystem.exists(self.target_home / path)
        ]
        if not existing:
            return None
        rescue = self.state.root / "rescues" / f"{self.identifiers.transaction_id()}-{label}"
        rescue.mkdir(parents=True, mode=0o700)
        index: Dict[str, str] = {}
        for number, relative in enumerate(existing):
            name = f"{number:06d}"
            self.filesystem.copy(
                self.target_home / relative,
                rescue / "backup" / name,
            )
            index[relative.as_posix()] = name
        self.state.json.write(
            rescue / "manifest.json",
            {"created_at": self.identifiers.now(), "paths": index},
        )
        return rescue
