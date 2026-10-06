import unittest

from ibus_latex.composer import Composer
from ibus_latex.symbols import load_table

TABLE = load_table()


def typed(composer, text):
    """Type characters one by one; return what was committed, if anything."""
    out = None
    for ch in text:
        out = composer.type_char(ch)
    return out


class ComposerTest(unittest.TestCase):
    def setUp(self):
        self.c = Composer(TABLE)
        self.c.start()

    def test_type_and_accept(self):
        self.assertIsNone(typed(self.c, "mapsto"))
        self.assertEqual(self.c.preedit, "\\mapsto")
        self.assertEqual(self.c.current.name, "mapsto")
        self.assertEqual(self.c.accept(), "↦")
        self.assertFalse(self.c.active)
        self.assertEqual(self.c.preedit, "")

    def test_prefix_accepts_best_match(self):
        typed(self.c, "rightarr")
        self.assertEqual(self.c.accept(), "→")

    def test_leading_backslash_ignored(self):
        typed(self.c, "\\alpha")
        self.assertEqual(self.c.preedit, "\\alpha")

    def test_terminator_commits_with_char(self):
        self.assertEqual(typed(self.c, "alpha("), "α(")
        self.assertFalse(self.c.active)

    def test_terminator_without_match_commits_raw_text(self):
        self.assertEqual(typed(self.c, "zzz,"), "\\zzz,")

    def test_symbols_continue_names(self):
        typed(self.c, "mathbb{R}")
        self.assertEqual(self.c.accept(), "ℝ")
        self.c.start()
        typed(self.c, "^2")
        self.assertEqual(self.c.accept(), "²")

    def test_digit_selects_from_page(self):
        typed(self.c, "map")
        second = self.c.candidates[1].text
        self.assertEqual(self.c.type_char("2"), second)

    def test_navigation(self):
        typed(self.c, "map")
        self.c.move(1)
        self.assertEqual(self.c.cursor, 1)
        self.c.move(-2)
        self.assertEqual(self.c.cursor, len(self.c.candidates) - 1)
        self.c.cursor = 0
        self.c.page(1)
        self.assertEqual(self.c.cursor, min(9, len(self.c.candidates) - 1))

    def test_no_match_keeps_session(self):
        typed(self.c, "qqqq")
        self.assertEqual(self.c.candidates, [])
        self.assertIsNone(self.c.accept())
        self.assertTrue(self.c.active)

    def test_backspace(self):
        typed(self.c, "ab")
        self.c.backspace()
        self.assertEqual(self.c.buffer, "a")
        self.c.backspace()
        self.c.backspace()
        self.assertFalse(self.c.active)

    def test_accept_on_empty_leaves(self):
        self.assertIsNone(self.c.accept())
        self.assertFalse(self.c.active)


if __name__ == "__main__":
    unittest.main()
