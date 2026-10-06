#!/usr/bin/env python3
"""Desktop side of setup.sh: add or remove the LaTeX input source.

GNOME keeps its input sources in org.gnome.desktop.input-sources; other
desktops that use IBus's own panel read org.freedesktop.ibus.general.
Every value changed here is first saved to
~/.config/ibus-latex/setup-state.json, so `disable` can put it back.

Commands:
    detect-layout          print the keyboard layout to install with
    suggest-toggle         print the toggle key a Hangul user already uses
    enable [--add] [--toggle-key KEY]
    disable
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

ENGINE = "latex"
SOURCE = ("ibus", ENGINE)
GNOME_SOURCES = "org.gnome.desktop.input-sources"
GNOME_KEYS = "org.gnome.desktop.wm.keybindings"
IBUS_GENERAL = "org.freedesktop.ibus.general"
HANGUL = "org.freedesktop.ibus.engine.hangul"
COMPONENT_DIRS = ("/usr/share/ibus/component", "/usr/local/share/ibus/component",
                  "/usr/pkg/share/ibus/component", "/opt/local/share/ibus/component")

# Toggle keys: modifiers go through an xkb "grp:" option (mutter turns it
# into input-source switching); other keys become a GNOME keybinding.
XKB_TOGGLES = {
    "ralt": "grp:toggle", "lalt": "grp:lalt_toggle",
    "rctrl": "grp:rctrl_toggle", "lctrl": "grp:lctrl_toggle",
    "caps": "grp:caps_toggle", "menu": "grp:menu_toggle",
}
KEYBINDING_TOGGLES = {"hangul": "Hangul"}
TOGGLE_KEYS = sorted(XKB_TOGGLES) + sorted(KEYBINDING_TOGGLES)
# ibus-hangul switch-keys entry -> our toggle key name
HANGUL_SWITCH_KEYS = {"Alt_R": "ralt", "Alt_L": "lalt", "Control_R": "rctrl",
                      "Control_L": "lctrl", "Caps_Lock": "caps", "Menu": "menu",
                      "Hangul": "hangul"}


def state_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "ibus-latex", "setup-state.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    path = state_path()
    if not state:
        if os.path.exists(path):
            os.remove(path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def settings(schema):
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema, True) is None:
        return None
    return Gio.Settings.new(schema)


def remember(state, s, key):
    """Save a key's current value once, before the first change."""
    name = "%s %s" % (s.props.schema_id, key)
    state.setdefault("saved", {}).setdefault(name, s.get_value(key).print_(True))


def saved_value(state, schema, key):
    text = state.get("saved", {}).get("%s %s" % (schema, key))
    return GLib.Variant.parse(None, text, None, None) if text else None


def is_gnome():
    desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
    if "GNOME" in desktops:
        return True
    if not os.environ.get("XDG_CURRENT_DESKTOP") and shutil.which("pgrep"):
        return subprocess.call(["pgrep", "-u", str(os.getuid()), "-x", "gnome-shell"],
                               stdout=subprocess.DEVNULL) == 0
    return False


# -- detect-layout -------------------------------------------------------

def installed_layout():
    for d in COMPONENT_DIRS:
        try:
            with open(os.path.join(d, ENGINE + ".xml"), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        layout = re.search(r"<layout>(.*?)</layout>", text)
        variant = re.search(r"<layout_variant>(.*?)</layout_variant>", text)
        if layout and layout.group(1):
            if variant and variant.group(1):
                return "%s+%s" % (layout.group(1), variant.group(1))
            return layout.group(1)
    return None


def system_layout():
    """The console/X11 layout from localectl or setxkbmap, if available."""
    for cmd, pattern in ((["localectl", "status"], r"X11 Layout:\s*([^\s,]+)"),
                         (["setxkbmap", "-query"], r"layout:\s*([^\s,]+)")):
        if not shutil.which(cmd[0]):
            continue
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        m = re.search(pattern, out)
        if m and m.group(1) not in ("(unset)", "n/a"):
            return m.group(1)
    return None


def detect_layout():
    layout = installed_layout()
    if layout:
        return layout
    if not is_gnome():
        return "default"  # IBus keeps whatever layout the desktop set
    s = settings(GNOME_SOURCES)
    if s is not None:
        for kind, ident in s.get_value("sources").unpack():
            if kind == "xkb":
                return ident
    layout = system_layout()
    if layout:
        return layout
    print("could not detect your keyboard layout; using 'us' (see --layout)",
          file=sys.stderr)
    return "us"


# -- suggest-toggle ------------------------------------------------------

def suggest_toggle():
    """If Hangul is an input source and toggles with a key we can reuse,
    print that key; otherwise print nothing."""
    if not is_gnome():
        return
    sources = settings(GNOME_SOURCES)
    hangul = settings(HANGUL)
    if sources is None or hangul is None:
        return
    if ("ibus", "hangul") not in sources.get_value("sources").unpack():
        return
    if any(o.startswith("grp:") for o in sources.get_strv("xkb-options")):
        return  # some switching key is already set up
    if hangul.get_boolean("disable-latin-mode"):
        return
    for key in hangul.get_string("switch-keys").split(","):
        name = HANGUL_SWITCH_KEYS.get(key.strip())
        if name:
            print(name)
            return


# -- enable --------------------------------------------------------------

def replace_or_add(items, new, is_layout, add):
    """Put new in place of the first plain layout, or append it."""
    items = list(items)
    if new in items:
        return items
    for i, item in enumerate(items):
        if is_layout(item) and not add:
            items[i] = new
            return items
    items.append(new)
    return items


def enable(add, toggle):
    state = load_state()
    if is_gnome():
        s = settings(GNOME_SOURCES)
        if s is None:
            sys.exit("GNOME input-source settings not found")
        sources = s.get_value("sources").unpack()
        new = replace_or_add(sources, SOURCE, lambda src: src[0] == "xkb", add)
        if new != sources:
            remember(state, s, "sources")
            s.set_value("sources", GLib.Variant("a(ss)", new))
            print("Input sources: " + ", ".join(i for _, i in new))
        if toggle:
            enable_toggle(state, s, toggle, ("ibus", "hangul") in new)
    else:
        s = settings(IBUS_GENERAL)
        if s is None:
            print("IBus settings not found; add 'LaTeX symbols' with ibus-setup.")
        else:
            for key in ("preload-engines", "engines-order"):
                engines = s.get_strv(key)
                if key == "engines-order" and not engines:
                    continue
                new = replace_or_add(engines, ENGINE, lambda e: e.startswith("xkb:"), add)
                if new != engines:
                    remember(state, s, key)
                    s.set_strv(key, new)
            print("IBus engines: " + ", ".join(s.get_strv("preload-engines")))
        if toggle:
            print("--toggle-key is only supported on GNOME; set IBus's "
                  "'Next input method' shortcut in ibus-setup instead.")
    Gio.Settings.sync()
    save_state(state)


def enable_toggle(state, sources, toggle, have_hangul):
    if toggle in XKB_TOGGLES:
        option = XKB_TOGGLES[toggle]
        options = sources.get_strv("xkb-options")
        new = [o for o in options if not o.startswith("grp:")] + [option]
        if new != options:
            remember(state, sources, "xkb-options")
            sources.set_strv("xkb-options", new)
    else:
        keys = settings(GNOME_KEYS)
        binding = KEYBINDING_TOGGLES[toggle]
        current = keys.get_strv("switch-input-source")
        if binding not in current:
            remember(state, keys, "switch-input-source")
            keys.set_strv("switch-input-source", current + [binding])
    print("%s now switches input sources" % toggle)

    hangul = settings(HANGUL)
    if have_hangul and hangul is not None:
        # Hangul is then only ever Korean; English is the LaTeX source.
        for key, value in (("disable-latin-mode", GLib.Variant("b", True)),
                           ("initial-input-mode", GLib.Variant("s", "hangul"))):
            if hangul.get_value(key) != value:
                remember(state, hangul, key)
                hangul.set_value(key, value)
        print("Hangul: always Korean (its own English mode is off)")


# -- disable -------------------------------------------------------------

def restore_list(current, original, ours):
    """Remove ours from current and give back entries ours replaced."""
    result = [x for x in current if x != ours]
    if original is None:
        return result
    for i, item in enumerate(original):
        if item not in result and item != ours:
            result.insert(min(i, len(result)), item)
    return result


def disable():
    state = load_state()
    s = settings(GNOME_SOURCES)
    if s is not None and SOURCE in s.get_value("sources").unpack():
        original = saved_value(state, GNOME_SOURCES, "sources")
        current = s.get_value("sources").unpack()
        if original is not None:
            new = restore_list(current, original.unpack(), SOURCE)
        else:
            # No record: put the engine's own layout back in its place.
            layout = installed_layout()
            new = [src if src != SOURCE else ("xkb", layout) for src in current]
            if not layout or layout == "default":
                new = [src for src in current if src != SOURCE]
        s.set_value("sources", GLib.Variant("a(ss)", new))
        print("Input sources: " + ", ".join(i for _, i in new))

    s = settings(IBUS_GENERAL)
    if s is not None:
        for key in ("preload-engines", "engines-order"):
            engines = s.get_strv(key)
            if ENGINE in engines:
                original = saved_value(state, IBUS_GENERAL, key)
                s.set_strv(key, restore_list(engines, original and original.unpack(), ENGINE))

    # Everything else setup changed goes back to its saved value.
    for name, text in state.get("saved", {}).items():
        schema, key = name.split(" ", 1)
        if (schema, key) in ((GNOME_SOURCES, "sources"), (IBUS_GENERAL, "preload-engines"),
                             (IBUS_GENERAL, "engines-order")):
            continue
        s = settings(schema)
        if s is not None:
            s.set_value(key, GLib.Variant.parse(None, text, None, None))
            print("Restored %s %s" % (schema, key))
    Gio.Settings.sync()
    save_state({})


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect-layout")
    sub.add_parser("suggest-toggle")
    p = sub.add_parser("enable")
    p.add_argument("--add", action="store_true",
                   help="add the source beside your layout instead of replacing it")
    p.add_argument("--toggle-key", choices=TOGGLE_KEYS)
    sub.add_parser("disable")
    args = parser.parse_args()

    if args.command == "detect-layout":
        print(detect_layout())
    elif args.command == "suggest-toggle":
        suggest_toggle()
    elif args.command == "enable":
        enable(args.add, args.toggle_key)
    else:
        disable()


if __name__ == "__main__":
    main()
