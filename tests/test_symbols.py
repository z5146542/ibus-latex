import os
import tempfile
import unittest

from ibus_latex.symbols import Symbol, load_table, parse_text


class SymbolTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_table()

    def text(self, name):
        sym = self.table.get(name)
        return sym.text if sym else None

    def test_standard_names(self):
        self.assertEqual(self.text("mapsto"), "↦")
        self.assertEqual(self.text("to"), "→")
        self.assertEqual(self.text("le"), "≤")
        self.assertEqual(self.text("implies"), "⟹")
        self.assertEqual(self.text("forall"), "∀")

    def test_greek_is_upright(self):
        self.assertEqual(self.text("alpha"), "α")
        self.assertEqual(self.text("Omega"), "Ω")
        # LaTeX's \phi and \epsilon are the "straight"/lunate forms.
        self.assertEqual(self.text("phi"), "ϕ")
        self.assertEqual(self.text("varphi"), "φ")

    def test_alphabets(self):
        self.assertEqual(self.text("mathbb{R}"), "ℝ")
        self.assertEqual(self.text("bbN"), "ℕ")
        self.assertEqual(self.text("mathbb{1}"), "𝟙")
        self.assertEqual(self.text("mathcal{B}"), "ℬ")
        self.assertEqual(self.text("mathfrak{g}"), "𝔤")
        self.assertEqual(self.text("BbbR"), "ℝ")

    def test_scripts(self):
        self.assertEqual(self.text("^2"), "²")
        self.assertEqual(self.text("_i"), "ᵢ")
        self.assertEqual(self.text("^alpha"), "ᵅ")

    def test_text_accents(self):
        self.assertEqual(self.text('"o'), "ö")
        self.assertEqual(self.text('"{o}'), "ö")
        self.assertEqual(self.text("'e"), "é")
        self.assertEqual(self.text("v{c}"), "č")
        self.assertEqual(self.text("H{o}"), "ő")
        self.assertEqual(self.text("c{c}"), "ç")
        self.assertEqual(self.text("ss"), "ß")
        self.assertIsNone(self.table.get('"q'))  # no precomposed q-umlaut

    def test_shared_name_lists_latex_meaning_first(self):
        found = [s.text for s in self.table.search("^o") if s.name == "^o"]
        self.assertEqual(found, ["ô", "ᵒ"])
        self.assertEqual(self.text("^2"), "²")

    def test_combining_accents(self):
        sym = self.table.get("vec")
        self.assertEqual(sym.text, "⃗")
        self.assertEqual(sym.display, "◌⃗")

    def test_search_ranking(self):
        names = [s.name for s in self.table.search("map")]
        self.assertEqual(names[0], "mapsto")
        self.assertIn("longmapsto", names)
        self.assertEqual(self.table.search("in")[0].name, "in")
        # Preferred standard names beat unicode-math names of equal length.
        self.assertEqual(self.table.search("subset")[0].name, "subset")

    def test_case_insensitive_matches_rank_lower(self):
        names = [s.name for s in self.table.search("delta")]
        self.assertEqual(names[0], "delta")
        self.assertEqual(names[1], "Delta")

    def test_prefixes(self):
        self.assertTrue(self.table.is_prefix("mathbb{"))
        self.assertTrue(self.table.is_prefix("^"))
        self.assertFalse(self.table.is_prefix("alpha("))

    def test_user_file_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "symbols.tsv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\n\\heart\t♥\nmapsto\tU+27FC\nbad line\n")
            table = load_table(user_file=path)
        self.assertEqual(table.get("heart").text, "♥")
        self.assertEqual(table.get("mapsto").text, "⟼")
        self.assertTrue(table.get("heart").preferred)
        self.assertEqual([s.text for s in table.symbols if s.name == "mapsto"], ["⟼"])

    def test_user_file_replaces_all_symbols_of_a_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "symbols.tsv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("^o\t°\n")
            table = load_table(user_file=path)
        self.assertEqual([s.text for s in table.symbols if s.name == "^o"], ["°"])


class ParseTextTest(unittest.TestCase):
    def test_codepoints(self):
        self.assertEqual(parse_text("U+21A6"), "↦")
        self.assertEqual(parse_text("U+0041 U+0301"), "Á")

    def test_literal(self):
        self.assertEqual(parse_text("↦"), "↦")
        self.assertEqual(parse_text("U+zz"), "U+zz")


class SymbolInfoTest(unittest.TestCase):
    def test_info(self):
        self.assertEqual(Symbol("mapsto", "↦").info,
                         "U+21A6 rightwards arrow from bar")


if __name__ == "__main__":
    unittest.main()
