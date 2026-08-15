# dotfiles

## structure

| Path | Purpose |
|---|---|
| `home/` | Canonical files copied into the active home |
| `dotfiles` | Thin executable entry point |
| `dotfiles_app/app.py` | CLI composition and argument parsing |
| `dotfiles_app/commands.py` | Command objects, shared command context, and command factory |
| `dotfiles_app/configuration.py` | Resolved application path configuration |
| `dotfiles_app/deployment.py` | Deployment planning, transactions, state, and restoration |
| `dotfiles_app/filesystem.py` | Symlink-aware filesystem and atomic JSON services |
| `dotfiles_app/system.py` | Platform detection, command execution, and Homebrew management |
| `dotfiles_app/ghostty.py` | Platform-specific Snap setup and Ghostty installation |
| `dotfiles_app/skills.py` | Repository-managed `npx skills` integration |
| `.dotfilesignore` | Repository-only paths excluded from home deployment |
| `Brewfile` | Cross-platform Homebrew package inventory |
| `tests/` | Standard-library unit tests using temporary homes |

Runtime state must remain outside the repository, normally in `${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles`.

## conventions

- Preserve the directory structure beneath `home/`; every leaf maps to the same relative path beneath `$HOME`.
- `home/.gitkeep` only retains the source root in Git and is intentionally not deployed.
- Keep repository metadata such as `home/skills-lock.json` in `.dotfilesignore`.
- Install third-party skills with `./dotfiles skills`; additions and removals must be non-interactive project operations under `home/.agents/skills/`.
- Review third-party skill instructions and scripts before deployment.
- Use transactional copies rather than links to the checkout.
- Keep the CLI dependency-free beyond Python 3 and operating-system bootstrap tools.
- Put packages in `Brewfile`, using `if OS.mac?` and `if OS.linux?` for platform-specific entries.
- Never add secrets or credentials beneath `home/`.
- Filesystem changes must be journaled and recoverable before active-home paths are replaced.
- Keep the entry point thin; add behavior to the responsible service class in `dotfiles_app/`.
- Implement new CLI operations as `CliCommand` classes and register them with `CommandFactory`.
- Use strategies for platform-specific behavior instead of adding package-manager conditionals.
- Inject filesystem, runner, console, factory, and platform services when behavior needs isolated testing.

## lookup

| Task | Location |
|---|---|
| Agent skill | `home/.agents/skills/<name>/SKILL.md` |
| Neovim | `home/.config/nvim` |
| Zsh | `home/.zshenv`, `home/.zprofile`, `home/.zshrc`, `home/.zimrc` |

## commands

```sh
./dotfiles install --dry-run
./dotfiles apply --dry-run
./dotfiles status
./dotfiles doctor
./dotfiles skills query "search terms"
./dotfiles skills list --json
python3 -m unittest discover -s tests -v
python3 -m py_compile dotfiles dotfiles_app/*.py
```

Use `--target-home` and `--state-dir` before the subcommand when exercising deployment behavior outside the real home.

## anti-patterns

- Do not directly modify the real home while testing the installer.
- Do not install repository-managed skills with `npx skills --global`.
- Do not commit an unreviewed third-party skill.
- Do not make a Git checkout immediately active through symlinks.
- Do not delete backups automatically.
- Do not run Homebrew installation as root.
