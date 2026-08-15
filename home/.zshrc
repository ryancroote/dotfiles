# Start configuration added by Zim Framework install {{{
#
# User configuration sourced by interactive shells
#

# -----------------
# Zsh configuration
# -----------------

#
# History
#

# Remove older command from the history if a duplicate is to be added.
setopt HIST_IGNORE_ALL_DUPS

#
# Input/output
#

# Set editor default keymap to emacs (`-e`) or vi (`-v`)
bindkey -e

# Prompt for spelling correction of commands.
#setopt CORRECT

# Customize spelling correction prompt.
#SPROMPT='zsh: correct %F{red}%R%f to %F{green}%r%f [nyae]? '

# Remove path separator from WORDCHARS.
WORDCHARS=${WORDCHARS//[\/]}

# --------------------
# Module configuration
# --------------------

#
# git
#

# Set a custom prefix for the generated aliases. The default prefix is 'G'.
#zstyle ':zim:git' aliases-prefix 'g'

#
# input
#

# Append `../` to your input for each `.` you type after an initial `..`
#zstyle ':zim:input' double-dot-expand yes

#
# termtitle
#

# Set a custom terminal title format using prompt expansion escape sequences.
# See http://zsh.sourceforge.net/Doc/Release/Prompt-Expansion.html#Simple-Prompt-Escapes
# If none is provided, the default '%n@%m: %~' is used.
#zstyle ':zim:termtitle' format '%1~'

#
# zsh-autosuggestions
#

# Disable automatic widget re-binding on each precmd. This can be set when
# zsh-users/zsh-autosuggestions is the last module in your ~/.zimrc.
ZSH_AUTOSUGGEST_MANUAL_REBIND=1

# Customize the style that the suggestions are shown with.
# See https://github.com/zsh-users/zsh-autosuggestions/blob/master/README.md#suggestion-highlight-style
#ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'

#
# zsh-syntax-highlighting
#

# Set what highlighters will be used.
# See https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/docs/highlighters.md
ZSH_HIGHLIGHT_HIGHLIGHTERS=(main brackets)

# Customize the main highlighter styles.
# See https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/docs/highlighters/main.md#how-to-tweak-it
#typeset -A ZSH_HIGHLIGHT_STYLES
#ZSH_HIGHLIGHT_STYLES[comment]='fg=242'

# ------------------
# Initialize modules
# ------------------

ZIM_HOME=${ZDOTDIR:-${HOME}}/.zim
ZIM_CONFIG_FILE=${ZIM_CONFIG_FILE:-${ZDOTDIR:-${HOME}}/.zimrc}

# Download the official Zim framework when it is missing.
if [[ ! -r ${ZIM_HOME}/zimfw.zsh ]]; then
  if (( ${+commands[curl]} )); then
    mkdir -p "${ZIM_HOME}"
    _zimfw_download="${ZIM_HOME}/zimfw.zsh.tmp.$$"
    if curl -fsSL -o "${_zimfw_download}" \
        https://github.com/zimfw/zimfw/releases/latest/download/zimfw.zsh; then
      mv "${_zimfw_download}" "${ZIM_HOME}/zimfw.zsh"
    else
      rm -f "${_zimfw_download}"
      print -u2 "dotfiles: unable to download Zim from its official release"
    fi
    unset _zimfw_download
  else
    print -u2 "dotfiles: curl is required to install Zim"
  fi
fi

# Install missing modules and refresh generated initialization when needed.
if [[ -r ${ZIM_HOME}/zimfw.zsh ]]; then
  if [[ ! -r ${ZIM_HOME}/init.zsh || ! ${ZIM_HOME}/init.zsh -nt ${ZIM_CONFIG_FILE} ]]; then
    source "${ZIM_HOME}/zimfw.zsh" init
  fi
fi

if [[ -r ${ZIM_HOME}/init.zsh ]]; then
  source "${ZIM_HOME}/init.zsh"
else
  print -u2 "dotfiles: Zim initialization is unavailable"
fi
# }}} End configuration added by Zim Framework install

# environment
export HOMEBREW_NO_ENV_HINTS=1
# history
export HISTFILE=~/.zsh_history
export HISTFILESIZE=1000000000
export HISTSIZE=1000000000

setopt INC_APPEND_HISTORY
export HISTTIMEFORMAT="[%F %T] "
setopt EXTENDED_HISTORY
setopt HIST_FIND_NO_DUPS
setopt HIST_EXPIRE_DUPS_FIRST

setopt NO_BEEP

if [[ $OSTYPE == darwin* ]]; then
  alias ls="ls -lahG"
else
  alias ls="ls -lah --color=auto"
fi

# pnpm uses different default global directories on macOS and Linux.
if [[ $OSTYPE == darwin* ]]; then
  export PNPM_HOME="$HOME/Library/pnpm"
else
  export PNPM_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/pnpm"
fi
typeset -U path PATH
path=("$PNPM_HOME" $path)
export PATH

export GOPATH="$HOME/go"
export EDITOR="nvim"
if (( ${+commands[zed]} )); then
  export VISUAL="zed"
else
  export VISUAL="$EDITOR"
fi

export PYENV_ROOT="$HOME/.pyenv"
if (( ${+commands[pyenv]} )); then
  eval "$(pyenv init - zsh)"
fi

# Initialize the prompt after Zim so Starship remains the active prompt.
if (( ${+commands[starship]} )); then
  eval "$(starship init zsh)"
fi
