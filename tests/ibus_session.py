"""Drive the engine through a real ibus-daemon.  Run via run-ibus-tests.sh,
which sets IBUS_ADDRESS and XDG_CONFIG_HOME to a private test instance."""

import os
import time
import unittest

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

M = IBus.ModifierType
CTRL_SHIFT = M.CONTROL_MASK | M.SHIFT_MASK
CONFIG_DIR = os.path.join(os.environ["XDG_CONFIG_HOME"], "ibus-latex")


class Client:
    def __init__(self):
        IBus.init()
        deadline = time.monotonic() + 10
        while True:
            self.bus = IBus.Bus()
            if self.bus.is_connected():
                break
            if time.monotonic() > deadline:
                raise RuntimeError("cannot connect to the test ibus-daemon")
            time.sleep(0.1)

        self.ic = self.bus.create_input_context("ibus-latex-test")
        caps = IBus.Capabilite
        self.ic.set_capabilities(caps.PREEDIT_TEXT | caps.AUXILIARY_TEXT
                                 | caps.LOOKUP_TABLE | caps.FOCUS)
        self.clear()
        self.ic.connect("commit-text", lambda _ic, t: self.commits.append(t.get_text()))
        self.ic.connect("update-preedit-text", self._on_preedit)
        self.ic.connect("update-preedit-text-with-mode",
                        lambda ic, t, cur, vis, _mode: self._on_preedit(ic, t, cur, vis))
        self.ic.connect("hide-preedit-text", lambda _ic: setattr(self, "_preedit", ""))
        self.ic.connect("update-lookup-table", self._on_table)
        self.ic.connect("hide-lookup-table", lambda _ic: setattr(self, "candidates", []))
        self.ic.connect("update-auxiliary-text",
                        lambda _ic, t, vis: setattr(self, "aux", t.get_text() if vis else ""))
        self.ic.connect("hide-auxiliary-text", lambda _ic: setattr(self, "aux", ""))
        self.ic.focus_in()
        # IBus defaults to one engine for all windows, so switch it globally.
        self.bus.set_global_engine("latex")

        # The engine process starts on demand; wait until it answers the hotkey.
        deadline = time.monotonic() + 15
        while not self.key(IBus.KEY_L, CTRL_SHIFT):
            if time.monotonic() > deadline:
                raise RuntimeError("engine did not start")
            self.pump(0.2)
        self.key(IBus.KEY_Escape)
        self.clear()

    def clear(self):
        self.commits = []
        self._preedit = ""
        self.candidates = []
        self.cursor = 0
        self.aux = ""

    @property
    def preedit(self):
        return self._preedit

    def _on_preedit(self, _ic, text, _cursor, visible):
        self._preedit = text.get_text() if visible else ""

    def _on_table(self, _ic, table, visible):
        n = table.get_number_of_candidates()
        self.candidates = [table.get_candidate(i).get_text() for i in range(n)] if visible else []
        self.cursor = table.get_cursor_pos()

    def pump(self, seconds=0.1):
        ctx = GLib.MainContext.default()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while ctx.pending():
                ctx.iteration(False)
            time.sleep(0.005)

    def key(self, keyval, state=0):
        handled = self.ic.process_key_event(keyval, 0, state)
        self.ic.process_key_event(keyval, 0, state | M.RELEASE_MASK)
        self.pump()
        return handled

    def type(self, text):
        for ch in text:
            if ch.isupper():
                self.key(IBus.KEY_Shift_L, 0)
            self.key(IBus.unicode_to_keyval(ch), M.SHIFT_MASK if ch.isupper() else 0)

    def hotkey(self):
        return self.key(IBus.KEY_L, CTRL_SHIFT)

    def refocus(self):
        self.ic.focus_out()
        self.ic.focus_in()
        self.pump()


class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Client()

    def setUp(self):
        self.c.clear()

    @staticmethod
    def symbol(candidate):
        return candidate.split("  ", 1)[0].lstrip("◌")

    def test_plain_keys_pass_through(self):
        self.assertFalse(self.c.key(IBus.KEY_a))
        self.assertEqual(self.c.commits, [])

    def test_mapsto(self):
        self.assertTrue(self.c.hotkey())
        self.assertEqual(self.c.preedit, "\\")
        self.c.type("mapsto")
        self.assertEqual(self.c.preedit, "\\mapsto")
        self.assertEqual(self.c.candidates[0], "↦  \\mapsto")
        self.assertIn("U+21A6", self.c.aux)
        self.assertTrue(self.c.key(IBus.KEY_space))
        self.assertEqual(self.c.commits, ["↦"])
        self.assertEqual(self.c.preedit, "")
        self.assertEqual(self.c.candidates, [])

    def test_shifted_letters(self):
        self.c.hotkey()
        self.c.type("Delta")
        self.c.key(IBus.KEY_Return)
        self.assertEqual(self.c.commits, ["Δ"])

    def test_punctuation_ends_and_is_kept(self):
        self.c.hotkey()
        self.c.type("alpha(")
        self.assertEqual(self.c.commits, ["α("])

    def test_digit_selects(self):
        self.c.hotkey()
        self.c.type("map")
        second = self.symbol(self.c.candidates[1])
        self.c.key(IBus.KEY_2)
        self.assertEqual(self.c.commits, [second])

    def test_tab_moves_highlight(self):
        self.c.hotkey()
        self.c.type("map")
        self.c.key(IBus.KEY_Tab)
        self.assertEqual(self.c.cursor, 1)
        second = self.symbol(self.c.candidates[1])
        self.c.key(IBus.KEY_Return)
        self.assertEqual(self.c.commits, [second])

    def test_alphabets_and_scripts(self):
        self.c.hotkey()
        self.c.type("mathbb{R}")
        self.c.key(IBus.KEY_space)
        self.c.hotkey()
        self.c.type("^2")
        self.c.key(IBus.KEY_space)
        self.assertEqual(self.c.commits, ["ℝ", "²"])

    def test_escape_cancels(self):
        self.c.hotkey()
        self.c.type("alpha")
        self.assertTrue(self.c.key(IBus.KEY_Escape))
        self.assertEqual(self.c.commits, [])
        self.assertEqual(self.c.preedit, "")
        self.assertFalse(self.c.key(IBus.KEY_a))

    def test_ctrl_key_cancels_and_passes_through(self):
        self.c.hotkey()
        self.c.type("al")
        self.assertFalse(self.c.key(IBus.KEY_c, M.CONTROL_MASK))
        self.assertEqual(self.c.commits, [])
        self.assertEqual(self.c.preedit, "")

    def test_ctrl_shift_u_is_left_alone(self):
        # Ctrl+Shift+U is IBus's unicode-hotkey, handled by ibus-daemon before
        # engines see keys (or by the toolkit without IBus).  The engine must
        # simply not swallow it.
        self.assertFalse(self.c.key(IBus.KEY_U, CTRL_SHIFT))
        self.assertEqual(self.c.preedit, "")
        self.assertEqual(self.c.commits, [])

    def test_dead_keys_still_work(self):
        self.assertTrue(self.c.key(IBus.KEY_dead_acute))
        self.c.key(IBus.KEY_e)
        self.assertEqual(self.c.commits, ["é"])

    def test_user_config_reload(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        symbols = os.path.join(CONFIG_DIR, "symbols.tsv")
        settings = os.path.join(CONFIG_DIR, "config.ini")
        try:
            with open(symbols, "w", encoding="utf-8") as f:
                f.write("heart\t♥\n")
            with open(settings, "w", encoding="utf-8") as f:
                f.write("[settings]\nhotkey = Control+backslash\n")
            self.c.refocus()
            self.assertFalse(self.c.hotkey())
            self.assertTrue(self.c.key(IBus.KEY_backslash, M.CONTROL_MASK))
            self.c.type("heart")
            self.c.key(IBus.KEY_space)
            self.assertEqual(self.c.commits, ["♥"])
        finally:
            for path in (symbols, settings):
                if os.path.exists(path):
                    os.remove(path)
            self.c.refocus()
        self.assertTrue(self.c.hotkey())
        self.c.key(IBus.KEY_Escape)


if __name__ == "__main__":
    unittest.main()
