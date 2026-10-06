"""The compose session: hotkey, type a name, pick a symbol.

This is the input-method logic without any IBus calls.  A frontend feeds it
keys and redraws from its state (preedit, candidates, cursor) afterwards.
Methods that can finish the session return the text to commit, or None.
"""

from __future__ import annotations

PAGE_SIZE = 9


class Composer:
    def __init__(self, table, page_size=PAGE_SIZE):
        self.table = table
        self.page_size = page_size
        self.active = False
        self.buffer = ""
        self.candidates = []
        self.cursor = 0

    # -- state ---------------------------------------------------------

    @property
    def preedit(self):
        return "\\" + self.buffer if self.active else ""

    @property
    def page_start(self):
        return self.cursor - self.cursor % self.page_size

    @property
    def current(self):
        if self.candidates:
            return self.candidates[self.cursor]
        return None

    def start(self):
        self.active = True
        self._set_buffer("")

    def cancel(self):
        self.active = False
        self._set_buffer("")

    def set_table(self, table):
        self.table = table
        if self.active:
            self._set_buffer(self.buffer)

    def _set_buffer(self, text):
        self.buffer = text
        self.candidates = self.table.search(text) if text else []
        self.cursor = 0

    def _finish(self, text):
        self.cancel()
        return text

    # -- input ---------------------------------------------------------

    def type_char(self, ch):
        """Handle a printable character.

        Letters always extend the name.  Other characters extend it only if
        some name continues that way (\\^2, \\mathbb{R}); otherwise digits
        1-9 pick from the current page, and anything else ends the session,
        committing the highlighted symbol followed by the character.
        """
        if ch == "\\" and not self.buffer:
            return None
        if (ch.isascii() and ch.isalpha()) or self.table.is_prefix(self.buffer + ch):
            self._set_buffer(self.buffer + ch)
            return None
        if ch in "123456789" and self.candidates:
            return self.select(int(ch) - 1)
        if self.candidates:
            return self._finish(self.current.text + ch)
        return self._finish(self.preedit + ch if self.buffer else ch)

    def backspace(self):
        if self.buffer:
            self._set_buffer(self.buffer[:-1])
        else:
            self.cancel()

    def accept(self):
        """Space/Enter: commit the highlighted symbol.

        With nothing typed this leaves compose mode; with no match it does
        nothing, so a typo can be fixed with Backspace.
        """
        if self.candidates:
            return self._finish(self.current.text)
        if not self.buffer:
            self.cancel()
        return None

    def select(self, index_in_page):
        """Commit the candidate at a position on the current page."""
        index = self.page_start + index_in_page
        if 0 <= index_in_page < self.page_size and index < len(self.candidates):
            return self._finish(self.candidates[index].text)
        return None

    def move(self, delta):
        """Move the highlight, wrapping around at either end."""
        if self.candidates:
            self.cursor = (self.cursor + delta) % len(self.candidates)

    def page(self, delta):
        if self.candidates:
            last = len(self.candidates) - 1
            self.cursor = max(0, min(last, self.page_start + delta * self.page_size))
