"""Object-oriented dotfiles management application."""

from .app import DotfilesApplication, main
from .core import DotfilesError
from .deployment import Deployment

__all__ = ["Deployment", "DotfilesApplication", "DotfilesError", "main"]
