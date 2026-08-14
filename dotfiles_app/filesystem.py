"""Filesystem operations used by transactional deployment."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .core import DotfilesError


class FileSystem:
    """Provides safe, symlink-aware filesystem operations."""

    @staticmethod
    def exists(path: Path) -> bool:
        return os.path.lexists(str(path))

    @staticmethod
    def mode(path: Path) -> int:
        return stat.S_IMODE(path.lstat().st_mode)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def metadata(self, path: Path, recursive: bool = True) -> Dict[str, Any]:
        """Return stable metadata without following symlinks."""
        if not self.exists(path):
            return {"kind": "absent"}
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            return {"kind": "symlink", "target": os.readlink(str(path))}
        if stat.S_ISREG(info.st_mode):
            return {
                "kind": "file",
                "mode": mode,
                "size": info.st_size,
                "sha256": self._sha256(path),
            }
        if stat.S_ISDIR(info.st_mode):
            result: Dict[str, Any] = {"kind": "directory", "mode": mode}
            if recursive:
                entries: List[Tuple[str, Dict[str, Any]]] = []
                for root, dirnames, filenames in os.walk(str(path), followlinks=False):
                    root_path = Path(root)
                    for name in list(dirnames):
                        child = root_path / name
                        if child.is_symlink():
                            dirnames.remove(name)
                            rel = child.relative_to(path).as_posix()
                            entries.append((rel, self.metadata(child, recursive=False)))
                        else:
                            rel = child.relative_to(path).as_posix() + "/"
                            entries.append((rel, self.metadata(child, recursive=False)))
                    for name in filenames:
                        child = root_path / name
                        rel = child.relative_to(path).as_posix()
                        entries.append((rel, self.metadata(child, recursive=False)))
                payload = json.dumps(sorted(entries), sort_keys=True, separators=(",", ":"))
                result["tree_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            return result
        return {"kind": "special", "mode": mode}

    @staticmethod
    def same(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        return dict(left) == dict(right)

    def remove(self, path: Path) -> None:
        if not self.exists(path):
            return
        if path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            shutil.rmtree(str(path))

    def copy(self, source: Path, destination: Path) -> None:
        """Copy one filesystem object without following symlinks."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.remove(destination)
        if source.is_symlink():
            os.symlink(os.readlink(str(source)), str(destination))
        elif source.is_dir():
            shutil.copytree(
                str(source),
                str(destination),
                symlinks=True,
                copy_function=shutil.copy2,
            )
        elif source.is_file():
            shutil.copy2(str(source), str(destination), follow_symlinks=False)
        else:
            raise DotfilesError(f"Unsupported filesystem object: {source}")

    def deploy_leaf(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".dotfiles-tmp-{os.getpid()}-{uuid.uuid4().hex}"
        try:
            if source.is_symlink():
                os.symlink(os.readlink(str(source)), str(temporary))
            elif source.is_file():
                shutil.copy2(str(source), str(temporary), follow_symlinks=False)
            else:
                raise DotfilesError(f"Source leaf is not a file or symlink: {source}")
            self.remove(destination)
            os.replace(str(temporary), str(destination))
        finally:
            self.remove(temporary)

    @staticmethod
    def is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def intersects(self, left: Path, right: Path) -> bool:
        return self.is_relative_to(left, right) or self.is_relative_to(right, left)


class JsonStore:
    """Reads and atomically writes JSON state files."""

    def __init__(self, filesystem: Optional[FileSystem] = None) -> None:
        self.filesystem = filesystem or FileSystem()

    def read(
        self,
        path: Path,
        default: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not path.exists():
            return dict(default or {})
        try:
            with path.open(encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise DotfilesError(f"Cannot read state file {path}: {error}") from error
        if not isinstance(value, dict):
            raise DotfilesError(f"State file is not a JSON object: {path}")
        return value

    def write(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
