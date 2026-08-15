# Initialize Homebrew from its standard macOS or Linux location.
typeset -U path PATH

if (( ${+commands[brew]} )); then
  _dotfiles_brew=${commands[brew]}
elif [[ -x /opt/homebrew/bin/brew ]]; then
  _dotfiles_brew=/opt/homebrew/bin/brew
elif [[ -x /usr/local/bin/brew ]]; then
  _dotfiles_brew=/usr/local/bin/brew
elif [[ -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
  _dotfiles_brew=/home/linuxbrew/.linuxbrew/bin/brew
elif [[ -x "$HOME/.linuxbrew/bin/brew" ]]; then
  _dotfiles_brew="$HOME/.linuxbrew/bin/brew"
fi

if [[ -n ${_dotfiles_brew:-} ]]; then
  eval "$("$_dotfiles_brew" shellenv)"

  if "$_dotfiles_brew" list --formula libpq >/dev/null 2>&1; then
    path=("$("$_dotfiles_brew" --prefix libpq)/bin" $path)
  fi
fi
unset _dotfiles_brew

# Optional macOS application integrations.
if [[ $OSTYPE == darwin* ]]; then
  _toolbox_scripts="$HOME/Library/Application Support/JetBrains/Toolbox/scripts"
  [[ -d "$_toolbox_scripts" ]] && path+=("$_toolbox_scripts")
  unset _toolbox_scripts

  [[ -r "$HOME/.orbstack/shell/init.zsh" ]] && source "$HOME/.orbstack/shell/init.zsh"
fi

export PATH
