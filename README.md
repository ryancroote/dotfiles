# dotfiles

A low-dependency, transactional manager for this repository's home-directory files and Homebrew packages.

## How it works

`home/` is the canonical source tree. A file at `home/.config/example/config` is deployed to `~/.config/example/config`. Directories are merged, so unrelated machine-local files can coexist with managed files.

Deployments use **copies, not live links to the checkout**. Editing or pulling this repository therefore cannot immediately break the active home. Each `apply` performs a preflight, backs up every replaced or removed path, records a journal, and then deploys files. An interrupted or bad deployment can be restored without relying on Git.

State and private backups are stored by default in:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/
```

The state directory is created with mode `0700`. Backups are retained until manually removed. Repository-only paths listed in `.dotfilesignore` are not copied into the active home. Ignore entries are relative to `home/`, support shell-style wildcards, and may include comments beginning with `#`.

## First installation

```sh
./dotfiles install
```

This command:

1. Detects the operating system.
2. Installs Linux prerequisites when Homebrew is absent.
3. Installs Homebrew when needed.
4. Runs the repository `Brewfile`.
5. Transactionally deploys `home/`.

Use `--yes` for unattended operation:

```sh
./dotfiles install --yes
```

Global path overrides must precede the command:

```sh
./dotfiles --target-home /tmp/test-home --state-dir /tmp/dotfiles-state apply --dry-run
```

### Linux prerequisites

On Ubuntu/Debian-family systems the bootstrap installs `build-essential`, `procps`, `curl`, `file`, and `git` with `apt-get`.

On Fedora-family systems it installs the `development-tools` group plus `procps-ng`, `curl`, `file`, and `git` with `dnf`.

Native package installation uses `sudo`; Homebrew itself is never installed as root. Unsupported Linux distributions receive manual prerequisite instructions rather than being modified.

## Daily workflow

Add or edit the canonical file beneath `home/`, preview the deployment, and apply it:

```sh
$EDITOR home/.zshrc
./dotfiles apply --dry-run
./dotfiles apply
```

Check whether the active home differs from the repository:

```sh
./dotfiles status
```

`status` reports conflicts, missing files, modified files, and stale files removed from `home/`. Active-home edits are not copied back automatically; move intentional changes into `home/` before applying again.

Inspect deployment history:

```sh
./dotfiles history
```

Run environment checks:

```sh
./dotfiles doctor
```

## Restore and recovery

Restore the state that existed before the latest deployment:

```sh
./dotfiles restore latest
```

A specific transaction in the active history can be selected:

```sh
./dotfiles history
./dotfiles restore 20250101T120000Z-abcd1234
```

Restoring a specific transaction reverses it and every newer active transaction. Restoration refuses to overwrite files changed after deployment. To preserve those changes in a rescue backup and restore anyway:

```sh
./dotfiles restore --force
```

If an apply was interrupted, the journal blocks additional applies until recovery:

```sh
./dotfiles restore --recover
```

If shell startup files are broken, start a clean shell and run recovery from the checkout:

```sh
/bin/bash --noprofile --norc
cd "$HOME/Projects/dotfiles"  # adjust to the checkout location
./dotfiles history
./dotfiles restore latest --yes
```

Transaction data is under `~/.local/state/dotfiles/transactions/`; forced-restore and interrupted-recovery snapshots are under `~/.local/state/dotfiles/rescues/`.

## Agent skills

Use the Python CLI to install skills into `home/.agents/skills/`:

```sh
./dotfiles skills find "typescript testing"
./dotfiles skills add owner/repo --skill skill-name
```

The command runs `npx skills` from `home/`, targets the universal `.agents/skills/` location, and uses copies so installed files can be committed. Global or alternate-agent installation flags are rejected to keep skills inside this repository.

Review every downloaded `SKILL.md` and any bundled scripts before committing or deploying them. Skills can instruct an agent to execute commands.

Other operations use the same command:

```sh
./dotfiles skills list --json
./dotfiles skills update --yes
./dotfiles skills remove skill-name --yes
```

`home/skills-lock.json` records installed skill sources for reproducible updates. It is committed to Git but excluded from home deployment by `.dotfilesignore`.

After adding or updating a skill, review and deploy it:

```sh
git diff -- home/.agents home/skills-lock.json
./dotfiles apply --dry-run
./dotfiles apply
```

Pi discovers the deployed skill from `~/.agents/skills/` after starting a new session. A skill can also be loaded explicitly with `/skill:<name>`.

## Homebrew packages

`Brewfile` is the package inventory:

```ruby
brew "git"

on_macos do
  cask "iterm2"
end

on_linux do
  brew "util-linux"
end
```

Install only packages without deploying files:

```sh
./dotfiles packages
```

Install or repair Homebrew without applying packages or files:

```sh
./dotfiles bootstrap
```

The CLI locates Homebrew in the standard Apple Silicon, Intel macOS, and Linuxbrew locations for the current run. Add the appropriate `brew shellenv` setup to a managed shell startup file if `brew` should be available in future interactive shells.

## Commands

| Command | Purpose |
|---|---|
| `install` | Bootstrap Homebrew, install the Brewfile, and apply dotfiles |
| `bootstrap` | Install platform prerequisites and Homebrew |
| `packages` | Run `brew bundle` for this repository |
| `apply` | Transactionally copy `home/` into the target home |
| `status` | Report active-home drift |
| `history` | List transactions and identify the active one |
| `restore` | Reverse one or more active transactions |
| `doctor` | Check platform and deployment health |
| `skills` | Manage repository skills through `npx skills` |

`install`, `bootstrap`, `packages`, and `apply` support `--dry-run`. Mutating commands that prompt support `--yes`.

## Development

The deployment implementation uses only the Python standard library. Node.js is installed through the Brewfile solely for `npx skills`. Run tests with:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile dotfiles
```

Tests always use temporary repository, home, and state directories.

## Secrets

Do not commit credentials, API tokens, private keys, machine-specific secrets, or unencrypted secret-bearing configuration beneath `home/`. Keep those in an external secret manager or machine-local files referenced by managed configuration.
