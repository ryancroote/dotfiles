# dotfiles

## structure

| Path | Purpose |
|---|---|
| `home/` | Canonical files copied into the active home |
| `dotfiles` | Standard-library Python deployment and bootstrap CLI |
| `Brewfile` | Cross-platform Homebrew package inventory |
| `tests/` | Standard-library unit tests using temporary homes |

Runtime state must remain outside the repository, normally in `${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles`.

## conventions

- Preserve the directory structure beneath `home/`; every leaf maps to the same relative path beneath `$HOME`.
- `home/.gitkeep` only retains the source root in Git and is intentionally not deployed.
- Use transactional copies rather than links to the checkout.
- Keep the CLI dependency-free beyond Python 3 and operating-system bootstrap tools.
- Put packages in `Brewfile`, using `on_macos` and `on_linux` for platform-specific entries.
- Never add secrets or credentials beneath `home/`.
- Filesystem changes must be journaled and recoverable before active-home paths are replaced.

## lookup

| Task | Location |
|---|---|
| Agent skill | `home/.agents/skills/<name>/README.md` |

## commands

```sh
./dotfiles install --dry-run
./dotfiles apply --dry-run
./dotfiles status
./dotfiles doctor
python3 -m unittest discover -s tests -v
python3 -m py_compile dotfiles
```

Use `--target-home` and `--state-dir` before the subcommand when exercising deployment behavior outside the real home.

## anti-patterns

- Do not directly modify the real home while testing the installer.
- Do not make a Git checkout immediately active through symlinks.
- Do not delete backups automatically.
- Do not run Homebrew installation as root.
