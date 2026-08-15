# Ghostty installation on Linux

Research date: 2026-08-15

## Question

How should this repository install Ghostty on Fedora and Ubuntu when Homebrew only provides the macOS cask?

## Findings

Ghostty only publishes official prebuilt binaries for macOS. Linux packages come from distribution or community maintainers, so there is no Linux equivalent to the official macOS Homebrew artifact. The Ghostty documentation recommends using an available package instead of building from source.

Source: [Ghostty: Prebuilt Binaries and Packages](https://ghostty.org/docs/install/binary)

### Snap: best common path for Fedora and Ubuntu

Ghostty documents a cross-distribution Snap installation:

```sh
sudo snap install ghostty --classic
```

The Snap is currently maintained externally, but Ghostty says it is built with Ghostty's own scripts and verified in Ghostty's CI. Ghostty is working to transfer the Snap into official project ownership. The Snap Store currently publishes stable builds for both `amd64` and `arm64`.

Sources:

- [Ghostty Linux Snap instructions](https://ghostty.org/docs/install/binary#snap)
- [Snap Store: Ghostty](https://snapcraft.io/ghostty)
- [Snap Store API: Ghostty release channels](https://api.snapcraft.io/v2/snaps/info/ghostty)

Ubuntu commonly includes `snapd`; otherwise it can be installed through APT. Fedora requires `snapd` setup and may require enabling its socket and creating `/snap` compatibility support.

Sources:

- [Snapcraft: Install snap on Ubuntu](https://snapcraft.io/docs/installing-snap-on-ubuntu)
- [Snapcraft: Install snap on Fedora](https://snapcraft.io/docs/installing-snap-on-fedora)

### Fedora alternative: COPR

Ghostty documents the community-maintained `scottames/ghostty` Fedora COPR:

```sh
sudo dnf copr enable scottames/ghostty
sudo dnf install ghostty
```

The COPR is not an official Fedora repository or an official Ghostty binary. Its current project metadata advertises Fedora 43, Fedora 44, and Rawhide builds for `x86_64` and `aarch64`.

Sources:

- [Ghostty Fedora instructions](https://ghostty.org/docs/install/binary#fedora)
- [Fedora COPR: scottames/ghostty](https://copr.fedorainfracloud.org/coprs/scottames/ghostty/)
- [Fedora COPR project API](https://copr.fedorainfracloud.org/api_3/project?ownername=scottames&projectname=ghostty)

### Ubuntu alternative: community `.deb`

Ghostty documents `mkasberg/ghostty-ubuntu`, which provides Ubuntu packages through a remote installation script. This is a community package and requires trusting a third-party script and package repository.

Source: [Ghostty Ubuntu instructions](https://ghostty.org/docs/install/binary#ubuntu)

### AppImage alternative

Ghostty lists a community-built AppImage that can run across Linux distributions. Ghostty explicitly warns that community binaries carry more supply-chain risk than official or distribution-maintained builds. AppImages would also require this repository to implement download, architecture selection, integrity checking, desktop integration, and updates.

Sources:

- [Ghostty community binaries](https://ghostty.org/docs/install/binary#linux-community-binaries)
- [pkgforge-dev/ghostty-appimage](https://github.com/pkgforge-dev/ghostty-appimage)

### Building from source

Building from source is the strongest option when third-party binaries are unacceptable, but Ghostty does not recommend it for most users. It requires an exact Ghostty-compatible Zig version plus GTK4, libadwaita, gtk4-layer-shell, pkg-config, and gettext development packages. Ghostty 1.3.x requires Zig 0.15.2. Ubuntu versions without `gtk4-layer-shell` must build that dependency too.

Ghostty publishes signed source tarballs and a Minisign public key, making a verified source installer possible. It would still be substantially more complex and slower than package installation.

Source: [Ghostty: Build from Source](https://ghostty.org/docs/install/build)

## Recommendation

Use a dedicated Ghostty installation strategy rather than adding it to Linuxbrew:

1. Keep `cask "ghostty" if OS.mac?` for macOS.
2. For Ubuntu and Fedora, prefer `snap install ghostty --classic` as the single cross-distribution path.
3. Treat Snap setup as an explicit system operation because Fedora requires a service and filesystem integration.
4. Check whether `ghostty` is already installed before adding Snap or changing the system.
5. Support `--dry-run` and the existing confirmation/`--yes` behavior.
6. Keep Fedora COPR as a documented alternative, not the automatic default.
7. Do not automate the Ubuntu `curl | bash` installer or community AppImage without explicit user selection.

The `GhosttyManager` service uses the existing platform Strategy pattern:

- macOS strategy: Homebrew Bundle owns Ghostty.
- Ubuntu strategy: ensure `snapd`, then install the classic Snap.
- Fedora strategy: ensure and enable `snapd`, then install the classic Snap.
- Unsupported strategy: print the official package documentation URL.

This keeps the Brewfile valid everywhere while making the non-Homebrew Linux exception explicit and testable.
