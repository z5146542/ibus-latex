"""Symbol tables: LaTeX command name -> Unicode text, and searching them.

Nothing here depends on IBus, so the table can be reused by other frontends.
"""

from __future__ import annotations

import os
import unicodedata

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(PACKAGE_DIR), "data")

# (file, preferred).  Names from preferred files rank ahead of the long tail
# of unicode-math names in search results.  A name may appear in several
# files with different symbols; the earlier file's symbol is listed first
# (\^o is ô from text.tsv, then superscript ᵒ from extra.tsv).
BUILTIN_TABLES = (
    ("unicode-math.tsv", False),
    ("latex.tsv", True),
    ("text.tsv", True),
    ("extra.tsv", True),
)

# unicode-math names for math alphabets -> extra spellings people type.
# Only single letters and digits get aliases (\mbfA, not \mbfitA).
ALPHABET_ALIASES = (
    ("Bbb", ("mathbb{%s}", "bb%s")),
    ("mscr", ("mathcal{%s}", "mathscr{%s}", "scr%s")),
    ("mfrak", ("mathfrak{%s}", "frak%s")),
    ("mbf", ("mathbf{%s}", "bf%s")),
    ("mit", ("mathit{%s}",)),
    ("msans", ("mathsf{%s}",)),
    ("mtt", ("mathtt{%s}",)),
)
DIGIT_WORDS = ("zero", "one", "two", "three", "four",
               "five", "six", "seven", "eight", "nine")

MAX_RESULTS = 100


class Symbol:
    __slots__ = ("name", "text", "description", "preferred", "folded")

    def __init__(self, name, text, description="", preferred=False):
        self.name = name
        self.text = text
        self.description = description
        self.preferred = preferred
        self.folded = name.casefold()

    def __repr__(self):
        return "Symbol(%r, %r)" % (self.name, self.text)

    @property
    def display(self):
        """The text as shown in a candidate list (marks get a dotted circle)."""
        if all(_invisible(c) for c in self.text):
            if all(unicodedata.combining(c) for c in self.text):
                return "◌" + self.text
            return " ".join("U+%04X" % ord(c) for c in self.text)
        return self.text

    @property
    def info(self):
        """One line describing the symbol: codepoints and Unicode name."""
        codes = " ".join("U+%04X" % ord(c) for c in self.text)
        names = [unicodedata.name(c, "") for c in self.text]
        if all(names):
            return "%s %s" % (codes, " + ".join(names).lower())
        if self.description:
            return "%s %s" % (codes, self.description)
        return codes


def _invisible(c):
    return unicodedata.combining(c) or unicodedata.category(c)[0] in "CZ"


def parse_text(field):
    """Parse a symbol column: literal text, or space separated U+XXXX codes."""
    parts = field.split()
    if parts and all(p[:2] in ("U+", "u+") and len(p) > 2 for p in parts):
        try:
            return "".join(chr(int(p[2:], 16)) for p in parts)
        except ValueError:
            pass
    return field


def read_tsv(path):
    """Yield (name, text, description) from a name<TAB>symbol[<TAB>desc] file.

    Blank lines and lines starting with '#' are ignored.  A leading
    backslash on the name is optional.
    """
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            name = cols[0].strip().lstrip("\\")
            text = parse_text(cols[1].strip())
            desc = cols[2].strip() if len(cols) > 2 else ""
            if name and text:
                yield name, text, desc


def alphabet_aliases(symbols):
    """Extra names like mathbb{R} and bbR for unicode-math's \\BbbR etc."""
    out = []
    for prefix, patterns in ALPHABET_ALIASES:
        for sym in symbols:
            name = sym.name
            if not name.startswith(prefix):
                continue
            rest = name[len(prefix):]
            if len(rest) == 1 and rest.isascii() and rest.isalpha():
                key = rest
            elif rest in DIGIT_WORDS:
                key = str(DIGIT_WORDS.index(rest))
            else:
                continue
            for pattern in patterns:
                out.append(Symbol(pattern % key, sym.text, sym.description))
    return out


class SymbolTable:
    def __init__(self, symbols):
        """symbols: Symbol objects, highest priority first.  A name can occur
        more than once with different text."""
        self.symbols = list(symbols)
        self._first = {}
        self._prefixes = set()
        for sym in self.symbols:
            self._first.setdefault(sym.name, sym)
            for i in range(1, len(sym.name) + 1):
                self._prefixes.add(sym.name[:i])

    def __len__(self):
        return len(self.symbols)

    def __contains__(self, name):
        return name in self._first

    def get(self, name):
        """The first symbol with this name."""
        return self._first.get(name)

    def is_prefix(self, text):
        """True if some name starts with text."""
        return text in self._prefixes

    def search(self, query, limit=MAX_RESULTS):
        """Symbols matching query, best first.

        Ranking: exact match, case-insensitive exact match, prefix,
        case-insensitive prefix, substring, case-insensitive substring.
        Within a group, preferred (standard LaTeX) names come first, then
        shorter names, then table order.
        """
        if not query:
            return []
        folded = query.casefold()
        ranked = []
        for order, sym in enumerate(self.symbols):
            name = sym.name
            if name == query:
                tier = 0
            elif sym.folded == folded:
                tier = 1
            elif name.startswith(query):
                tier = 2
            elif sym.folded.startswith(folded):
                tier = 3
            elif query in name:
                tier = 4
            elif folded in sym.folded:
                tier = 5
            else:
                continue
            ranked.append((tier, not sym.preferred, len(name), name, order, sym))
        ranked.sort(key=lambda r: r[:5])
        return [r[5] for r in ranked[:limit]]


def load_table(data_dir=DATA_DIR, user_file=None):
    """Build the table from the bundled data plus an optional user file.

    The same name and symbol from a later file replaces the earlier entry in
    place (so standard LaTeX names in latex.tsv become preferred); the user
    file replaces every built-in symbol of a name it defines.
    """
    symbols = {}  # (name, text) -> Symbol, in priority order

    def add(sym, override=False):
        if override:
            for key in [k for k in symbols if k[0] == sym.name]:
                del symbols[key]
        old = symbols.get((sym.name, sym.text))
        if old is not None and not sym.description:
            sym.description = old.description
        symbols[(sym.name, sym.text)] = sym

    for filename, preferred in BUILTIN_TABLES:
        path = os.path.join(data_dir, filename)
        for name, text, desc in read_tsv(path):
            add(Symbol(name, text, desc, preferred))
        if filename == "unicode-math.tsv":
            names = {name for name, _ in symbols}
            for sym in alphabet_aliases(list(symbols.values())):
                if sym.name not in names:
                    add(sym)

    if user_file and os.path.isfile(user_file):
        for name, text, desc in read_tsv(user_file):
            add(Symbol(name, text, desc, preferred=True), override=True)

    return SymbolTable(symbols.values())
