"""User configuration under $XDG_CONFIG_HOME/ibus-latex/.

config.ini
    [settings]
    hotkey = Control+Shift+l

symbols.tsv
    Extra or overriding symbols, one name<TAB>symbol per line.
"""

from __future__ import annotations

import configparser
import os

DEFAULT_HOTKEY = "Control+Shift+l"


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(base, "ibus-latex")


def config_file():
    return os.path.join(config_dir(), "config.ini")


def user_symbols_file():
    return os.path.join(config_dir(), "symbols.tsv")


def mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def load_settings(path=None):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path or config_file(), encoding="utf-8")
    except configparser.Error:
        pass
    return {
        "hotkey": parser.get("settings", "hotkey", fallback=DEFAULT_HOTKEY).strip()
        or DEFAULT_HOTKEY,
    }
