# ibus-latex

Type Unicode symbols by their LaTeX names, anywhere you can type text.

Press **Ctrl+Shift+L**, type `mapsto`, press **Space**: you get `↦`.
It works like IBus's Ctrl+Shift+U, but you type names instead of hex codes,
and a candidate list completes as you type:

```
\map▏
 1 ↦  \mapsto        U+21A6 rightwards arrow from bar
 2 ↥  \mapsup
 3 ↧  \mapsdown
 4 ↤  \mapsfrom
 5 ⤇  \Mapsto
 …
```

Outside compose mode the engine behaves exactly like a plain keyboard layout,
so `\alpha` typed normally stays `\alpha` (handy in `.tex` files). Dead keys,
Compose, and IBus's own Ctrl+Shift+U and emoji shortcuts keep working.

## Keys

| Key | In compose mode |
| --- | --- |
| Ctrl+Shift+L | start (press again to cancel) |
| letters, `^ _ { }` … | type the name (a leading `\` is optional) |
| Space, Enter | insert the highlighted symbol |
| 1–9 | insert that candidate from the current page |
| Tab, Shift+Tab, ↑, ↓ | move the highlight |
| Page Up / Page Down | change page |
| Backspace | delete a character (on an empty name: cancel) |
| Esc | cancel |
| other punctuation | insert the highlighted symbol, then that character (`\alpha(` → `α(`) |
| Ctrl/Alt shortcuts, arrows | cancel and pass the key on |

If nothing matches, Space and Enter do nothing, so you can fix a typo.

## What names work

About 3,300 names:

- **Standard LaTeX and amssymb names** (`\to`, `\le`, `\implies`, `\forall`,
  `\alpha` … `\Omega`). These rank first. Greek letters are the plain
  upright ones you would use in text (`α`, not `𝛼`). As in LaTeX, `\epsilon`
  is `ϵ` and `\varepsilon` is `ε`; `\phi` is `ϕ` and `\varphi` is `φ`.
- **Every unicode-math command** (2,448 of them, e.g. `\BbbR`, `\mbfA`,
  `\leftrightarrowtriangle`).
- **Math alphabets**: `\mathbb{R}` / `\bbR` → `ℝ`, `\mathcal{L}` → `ℒ`,
  `\mathfrak{g}` → `𝔤`, `\mathbf{x}`, `\mathit`, `\mathsf`, `\mathtt`, and
  digits, e.g. `\mathbb{1}` → `𝟙`.
- **Super- and subscripts** in the Julia REPL style: `\^2` → `²`,
  `\_i` → `ᵢ`, `\^alpha` → `ᵅ` (Unicode only has some letters).
- **Combining accents**: type the letter first, then `\vec`, `\hat`, `\bar`,
  `\tilde`, `\dot` … (`x` + `\vec` → `x⃗`).

The search matches prefixes and substrings, so `\arrow` lists every arrow.

## Requirements

- IBus 1.5 or newer, set up as your input method.
- Python 3.8 or newer with PyGObject and the IBus typelib:

| System | Packages |
| --- | --- |
| Debian, Ubuntu | `python3-gi gir1.2-ibus-1.0` |
| Fedora, RHEL | `python3-gobject ibus-libs` |
| Arch | `python-gobject ibus` |
| openSUSE | `python3-gobject typelib-1_0-IBus-1_0` |
| Alpine | `py3-gobject3 ibus` |
| FreeBSD | `ibus py311-gobject3` (match your Python version) |

TeX is **not** needed: the symbol table is included in `data/`.

## Install

```sh
git clone <this repository> ibus-latex
cd ibus-latex
./install.sh                 # just for you, no root needed
# or
sudo ./install.sh --system   # for every user
```

Then add **LaTeX symbols** as an input source:

- **GNOME**: Settings → Keyboard → Input Sources → Add → English → LaTeX
  symbols. To replace an existing layout with it from the shell instead
  (keep any other sources you have in the list):
  `gsettings set org.gnome.desktop.input-sources sources "[('ibus', 'latex')]"`
- **KDE, Xfce, i3, sway, …** (any desktop running IBus): `ibus-setup` →
  Input Method → Add → English → LaTeX symbols, or `ibus engine latex`.

The engine replaces your plain keyboard layout rather than sitting beside
it, because IBus only sends keys to the active engine. It types exactly like
that layout until you press the hotkey.

### Keyboard layout

`--layout` sets the layout used while the engine is active, e.g.
`./install.sh --layout gb` or `--layout de+nodeadkeys`. Without it the
installer reuses the layout of a previous install, or GNOME's first keyboard
layout, or `default`, which keeps whatever layout is already active (the right
choice on KDE and most non-GNOME desktops). On GNOME, set it explicitly if
you change layouts.

### How the per-user install works

IBus only reads engine definitions from its own `share/ibus/component`
directory, or from the directories listed in `IBUS_COMPONENT_PATH`. A
per-user install therefore sets `IBUS_COMPONENT_PATH` to IBus's directory
plus `~/.local/share/ibus-latex/component`:

- On systemd sessions (GNOME, KDE and most distributions) it writes
  `~/.config/environment.d/60-ibus-latex.conf` and restarts IBus right away.
- Elsewhere it prints a line to add to `~/.profile`
  (`. ~/.local/share/ibus-latex/env.sh`); log out and back in afterwards.

`sudo ./install.sh --system` avoids all of this by putting the definition in
IBus's own directory; afterwards run `ibus restart` as your normal user.

### Uninstall

```sh
./install.sh --uninstall            # or: sudo ./install.sh --system --uninstall
```

## Configuration

Files in `~/.config/ibus-latex/` (or `$XDG_CONFIG_HOME/ibus-latex/`) are
re-read automatically when a window gains focus.

`config.ini` changes the hotkey:

```ini
[settings]
hotkey = Control+Shift+l
```

Modifiers: `Control`, `Shift`, `Alt`, `Super`. Keys use X keysym names
(`l`, `backslash`, `space`, `F12`, …).

`symbols.tsv` adds your own names or overrides built-in ones. Each line is
a name, a Tab, and a symbol, either literally or as `U+XXXX` code points:

```
# name<TAB>symbol
heart	♥
qed	∎
iff	U+21D4
```

## Compatibility

- **Linux**: any distribution and desktop where IBus is the input method,
  on X11 or Wayland. Tested on Fedora 44 with GNOME 50 (Wayland). The
  installer is plain POSIX `sh` (checked with dash and ShellCheck).
- **FreeBSD, OpenBSD, NetBSD**: IBus and PyGObject are packaged there, and the
  installer looks in `/usr/local` and `/usr/pkg`. It should work, but has not
  been tested.
- **Fcitx5**: not supported. Fcitx5 cannot load IBus engines; it would need
  its own frontend. `ibus_latex/symbols.py` and `ibus_latex/composer.py`
  hold the input-method logic and do not depend on IBus, so a frontend would
  only need to adapt the key handling.
- **macOS, Windows**: no IBus. The same goes for apps that bypass the input
  method (some games, remote desktops, virtual machines).

## Development

```sh
python3 -m unittest discover -s tests   # logic tests, no IBus needed
tests/run-ibus-tests.sh                 # end-to-end, private ibus-daemon
./ibus-engine-latex                     # run from the tree as engine "latex-dev";
ibus engine latex-dev                   #   then switch to it to try it out
```

`tests/run-ibus-tests.sh` starts its own `ibus-daemon` inside
`dbus-run-session` with separate config and cache directories, so it does not
touch your desktop's IBus. It drives the engine the way an application would.

Set `IBUS_LATEX_DEBUG=1` in the environment of `ibus-daemon` for debug logs.

To refresh `data/unicode-math.tsv` from a newer TeX Live:

```sh
tools/gen_unicode_math.py > data/unicode-math.tsv
```

### Layout

```
ibus_latex/symbols.py    symbol tables and search (no IBus)
ibus_latex/composer.py   compose-mode state machine (no IBus)
ibus_latex/engine.py     IBus engine: keys, preedit, candidate list
ibus_latex/main.py       process entry point / engine factory
data/latex.tsv           standard LaTeX names (hand-maintained, ranked first)
data/extra.tsv           super/subscripts
data/unicode-math.tsv    generated from unicode-math-table.tex
component/latex.xml.in   IBus engine definition template
install.sh               POSIX installer
```

## License

MIT for the code (see `LICENSE`). `data/unicode-math.tsv` is derived from
`unicode-math-table.tex` in the [unicode-math](https://github.com/latex3/unicode-math)
package, which is distributed under the LaTeX Project Public License 1.3c.
