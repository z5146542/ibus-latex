"""IBus engine: the Composer behind a hotkey.

The engine subclasses IBus's own simple engine, so while compose mode is off
every key goes to the stock behaviour (plain typing, dead keys, Compose,
Ctrl+Shift+U).
"""

from __future__ import annotations

import logging

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from . import config  # noqa: E402
from .composer import Composer  # noqa: E402
from .symbols import load_table  # noqa: E402

log = logging.getLogger(__name__)

M = IBus.ModifierType
SUPER_BITS = M.SUPER_MASK | M.MOD4_MASK
# Modifiers that make a key a command (Ctrl+C) rather than text.
COMMAND_MASK = M.CONTROL_MASK | M.MOD1_MASK | SUPER_BITS | M.HYPER_MASK | M.META_MASK
HOTKEY_MASK = COMMAND_MASK | M.SHIFT_MASK

MODIFIER_NAMES = {
    "control": M.CONTROL_MASK, "ctrl": M.CONTROL_MASK, "primary": M.CONTROL_MASK,
    "shift": M.SHIFT_MASK,
    "alt": M.MOD1_MASK, "mod1": M.MOD1_MASK,
    "super": SUPER_BITS, "mod4": SUPER_BITS, "win": SUPER_BITS,
    "hyper": M.HYPER_MASK, "meta": M.META_MASK,
}

MODIFIER_KEYS = frozenset((
    IBus.KEY_Shift_L, IBus.KEY_Shift_R, IBus.KEY_Control_L, IBus.KEY_Control_R,
    IBus.KEY_Alt_L, IBus.KEY_Alt_R, IBus.KEY_Meta_L, IBus.KEY_Meta_R,
    IBus.KEY_Super_L, IBus.KEY_Super_R, IBus.KEY_Hyper_L, IBus.KEY_Hyper_R,
    IBus.KEY_Caps_Lock, IBus.KEY_Shift_Lock, IBus.KEY_Num_Lock,
    IBus.KEY_ISO_Level3_Shift, IBus.KEY_ISO_Level5_Shift, IBus.KEY_Mode_switch,
    IBus.KEY_ISO_Next_Group, IBus.KEY_ISO_Prev_Group,
))
ACCEPT_KEYS = frozenset((IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter,
                         IBus.KEY_space, IBus.KEY_KP_Space))
NEXT_KEYS = frozenset((IBus.KEY_Tab, IBus.KEY_Down, IBus.KEY_KP_Down))
PREV_KEYS = frozenset((IBus.KEY_ISO_Left_Tab, IBus.KEY_Up, IBus.KEY_KP_Up))
PAGE_DOWN_KEYS = frozenset((IBus.KEY_Page_Down, IBus.KEY_KP_Page_Down))
PAGE_UP_KEYS = frozenset((IBus.KEY_Page_Up, IBus.KEY_KP_Page_Up))


def _modifiers(state):
    mods = int(state) & HOTKEY_MASK
    if mods & SUPER_BITS:
        mods |= SUPER_BITS
    return mods


def _keyval_char(keyval):
    """The printable character a key types, or ''."""
    ch = IBus.keyval_to_unicode(keyval)
    if isinstance(ch, int):  # gunichar is an int in some older bindings
        ch = chr(ch) if ch else ""
    return ch if ch and ch.isprintable() else ""


def parse_hotkey(spec):
    """'Control+Shift+l' -> (keyval, modifiers), or None if it is not valid."""
    parts = [p.strip() for p in spec.split("+")]
    if not parts or not parts[-1]:
        return None
    mods = 0
    for part in parts[:-1]:
        bit = MODIFIER_NAMES.get(part.lower())
        if bit is None:
            return None
        mods |= int(bit)
    keyval = IBus.keyval_from_name(parts[-1])
    if keyval in (0, IBus.KEY_VoidSymbol):
        return None
    return IBus.keyval_to_lower(keyval), _modifiers(mods)


class Resources:
    """Symbol table and hotkey, shared by all engines of this process and
    reloaded when the user's files change."""

    def __init__(self):
        self.table = None
        self.hotkey = None
        self._stamp = None
        self.refresh()

    def refresh(self):
        symbols_file = config.user_symbols_file()
        stamp = (config.mtime(symbols_file), config.mtime(config.config_file()))
        if stamp == self._stamp:
            return
        if self._stamp is None or stamp[0] != self._stamp[0]:
            self.table = load_table(user_file=symbols_file)
            log.debug("loaded %d symbols", len(self.table))
        spec = config.load_settings()["hotkey"]
        hotkey = parse_hotkey(spec)
        if hotkey is None:
            log.warning("invalid hotkey %r, using %s", spec, config.DEFAULT_HOTKEY)
            hotkey = parse_hotkey(config.DEFAULT_HOTKEY)
        self.hotkey = hotkey
        self._stamp = stamp


class LatexEngine(IBus.EngineSimple):
    __gtype_name__ = "IBusLatexEngine"

    def __init__(self, resources, **kwargs):
        super().__init__(**kwargs)
        self._resources = resources
        self._composer = Composer(resources.table)

    # -- helpers -------------------------------------------------------

    def _sync_resources(self):
        self._resources.refresh()
        if self._composer.table is not self._resources.table:
            self._composer.set_table(self._resources.table)

    def _is_hotkey(self, keyval, state):
        hotkey_keyval, hotkey_mods = self._resources.hotkey
        return (IBus.keyval_to_lower(keyval) == hotkey_keyval
                and _modifiers(state) == hotkey_mods)

    def _chain_key(self, keyval, keycode, state):
        return IBus.EngineSimple.do_process_key_event(self, keyval, keycode, state)

    def _abandon(self):
        if self._composer.active:
            self._composer.cancel()
            self._update()

    def _update(self):
        c = self._composer
        if not c.active:
            self.hide_lookup_table()
            self.hide_auxiliary_text()
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(""), 0, False, IBus.PreeditFocusMode.CLEAR)
            return

        preedit = c.preedit
        text = IBus.Text.new_from_string(preedit)
        text.append_attribute(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE,
                              0, len(preedit))
        self.update_preedit_text_with_mode(
            text, len(preedit), True, IBus.PreeditFocusMode.CLEAR)

        if c.candidates:
            table = IBus.LookupTable.new(c.page_size, 0, True, False)
            table.set_orientation(IBus.Orientation.VERTICAL)
            for i in range(c.page_size):
                table.set_label(i, IBus.Text.new_from_string(str(i + 1)))
            for sym in c.candidates:
                table.append_candidate(
                    IBus.Text.new_from_string("%s  \\%s" % (sym.display, sym.name)))
            table.set_cursor_pos(c.cursor)
            self.update_lookup_table(table, True)
            aux = c.current.info
        else:
            self.hide_lookup_table()
            aux = "no match" if c.buffer else "type a LaTeX name, e.g. mapsto"
        self.update_auxiliary_text(IBus.Text.new_from_string(aux), True)

    def _finish(self, commit):
        self._update()
        if commit:
            self.commit_text(IBus.Text.new_from_string(commit))

    # -- keys ----------------------------------------------------------

    def do_process_key_event(self, keyval, keycode, state):
        c = self._composer
        released = state & M.RELEASE_MASK

        if not c.active:
            if not released and self._is_hotkey(keyval, state):
                IBus.EngineSimple.do_reset(self)
                self._sync_resources()
                c.start()
                self._update()
                return True
            return self._chain_key(keyval, keycode, state)

        if released or keyval in MODIFIER_KEYS:
            return True
        if keyval == IBus.KEY_Escape or self._is_hotkey(keyval, state):
            self._abandon()
            return True
        if state & COMMAND_MASK:
            # Ctrl+C and friends: leave compose mode, let the key through.
            self._abandon()
            return self._chain_key(keyval, keycode, state)

        commit = None
        if keyval == IBus.KEY_BackSpace:
            c.backspace()
        elif keyval in ACCEPT_KEYS:
            commit = c.accept()
        elif keyval in NEXT_KEYS:
            c.move(1)
        elif keyval in PREV_KEYS:
            c.move(-1)
        elif keyval in PAGE_DOWN_KEYS:
            c.page(1)
        elif keyval in PAGE_UP_KEYS:
            c.page(-1)
        else:
            ch = _keyval_char(keyval)
            if not ch:
                # Arrows, Home, F-keys...: give up and let the key through.
                self._abandon()
                return self._chain_key(keyval, keycode, state)
            commit = c.type_char(ch)
        self._finish(commit)
        return True

    # -- candidate window (mouse) ----------------------------------------

    def do_candidate_clicked(self, index, button, state):
        if not self._composer.active:
            return IBus.EngineSimple.do_candidate_clicked(self, index, button, state)
        self._finish(self._composer.select(index))

    def do_page_up(self):
        if not self._composer.active:
            return IBus.EngineSimple.do_page_up(self)
        self._composer.page(-1)
        self._update()

    def do_page_down(self):
        if not self._composer.active:
            return IBus.EngineSimple.do_page_down(self)
        self._composer.page(1)
        self._update()

    def do_cursor_up(self):
        if not self._composer.active:
            return IBus.EngineSimple.do_cursor_up(self)
        self._composer.move(-1)
        self._update()

    def do_cursor_down(self):
        if not self._composer.active:
            return IBus.EngineSimple.do_cursor_down(self)
        self._composer.move(1)
        self._update()

    # -- lifecycle -----------------------------------------------------

    def do_focus_in(self):
        self._sync_resources()
        IBus.EngineSimple.do_focus_in(self)

    def do_focus_out(self):
        self._abandon()
        IBus.EngineSimple.do_focus_out(self)

    def do_reset(self):
        self._abandon()
        IBus.EngineSimple.do_reset(self)

    def do_disable(self):
        self._abandon()
        IBus.EngineSimple.do_disable(self)
