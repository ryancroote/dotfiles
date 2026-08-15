# Keep user-local tools available to every Zsh invocation.
typeset -U path PATH
path=("$HOME/bin" "$HOME/.local/bin" $path)
export PATH

# Rust is optional and may be installed outside Homebrew.
[[ -r "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
