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

About 3,900 names:

- **Standard LaTeX and amssymb names** (`\to`, `\le`, `\implies`, `\forall`,
  `\alpha` … `\Omega`). These rank first. Greek letters are the plain
  upright ones you would use in text (`α`, not `𝛼`). As in LaTeX, `\epsilon`
  is `ϵ` and `\varepsilon` is `ε`; `\phi` is `ϕ` and `\varphi` is `φ`.
- **Every unicode-math command** (2,448 of them, e.g. `\BbbR`, `\mbfA`,
  `\leftrightarrowtriangle`).
- **Math alphabets**: `\mathbb{R}` / `\bbR` → `ℝ`, `\mathcal{L}` → `ℒ`,
  `\mathfrak{g}` → `𝔤`, `\mathbf{x}`, `\mathit`, `\mathsf`, `\mathtt`, and
  digits, e.g. `\mathbb{1}` → `𝟙`.
- **Text accents and letters** as in LaTeX: `\"o` or `\"{o}` → `ö`,
  `\'e` → `é`, `` \`a `` → `à`, `\^o` → `ô`, `\~n` → `ñ`, `\=a` → `ā`,
  `\.z` → `ż`; letter-named accents take braces: `\v{c}` → `č`,
  `\c{c}` → `ç`, `\H{o}` → `ő`, `\u{g}` → `ğ`, `\k{a}` → `ą`,
  `\r{a}` → `å`. Also `\ss` → `ß`, `\ae`, `\oe`, `\o`, `\l`, `\aa`,
  `\th`, `\textemdash`, `\texteuro`, `\guillemotleft` and similar. On
  layouts with dead keys, the dead `"` `'` `` ` `` `^` `~` keys work too.
- **Super- and subscripts** in the Julia REPL style: `\^2` → `²`,
  `\_i` → `ᵢ`, `\^alpha` → `ᵅ` (Unicode only has some letters). Where a
  name has both meanings, the LaTeX one comes first: `\^o` lists `ô`, then
  `ᵒ` (press `2` for it).
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
./setup.sh
```

Run it as your normal user. It asks for your password once and:

1. installs IBus and Python's GObject bindings if they are missing (apt, dnf,
   pacman, zypper, apk, xbps or FreeBSD pkg), after asking;
2. detects your keyboard layout and installs the engine system-wide;
3. restarts IBus;
4. makes **LaTeX symbols** your English input source. On GNOME it takes the
   place of your first keyboard layout; on other desktops it does the same
   in IBus's own engine list. `--add` keeps both instead;
5. if Hangul is one of your input sources and you switch Korean/English with
   a key inside it (e.g. Right Alt), offers to make that key switch between
   Hangul and English+LaTeX instead (see below).

Then press Ctrl+Shift+L, type `mapsto`, and press Space.

`./setup.sh --uninstall` undoes everything, putting back each setting it
changed. `./setup.sh --help` lists the options (`--layout`, `--add`,
`--toggle-key`, `--yes`).

The engine replaces your plain keyboard layout rather than sitting beside
it, because IBus only sends keys to the active engine. It types exactly like
that layout until you press the hotkey.

If IBus is not your input method yet (some non-GNOME desktops), make it so
first and log in again: on Debian/Ubuntu `im-config -n ibus`, on KDE System
Settings → Keyboard → Virtual Keyboard → IBus Wayland.

### With a Korean, Japanese or Chinese engine

If you switch languages with a key inside that engine (e.g. the Hangul key
or Right Alt in ibus-hangul), the engine's own English mode cannot have the
LaTeX hotkey. Instead, the key should switch between two input sources, the
CJK engine and LaTeX symbols. `setup.sh` offers this for Hangul, or ask for it
with `--toggle-key KEY` (`ralt`, `lalt`, `rctrl`, `lctrl`, `caps`, `menu`,
`hangul`; GNOME only). For Hangul it also turns off ibus-hangul's English
mode, so Hangul is always Korean. Escape in Korean then no longer switches
to English.

Doing the same by hand on GNOME, for Right Alt:

```sh
gsettings set org.gnome.desktop.input-sources sources "[('ibus', 'hangul'), ('ibus', 'latex')]"
gsettings set org.gnome.desktop.input-sources xkb-options "['grp:toggle']"   # Right Alt switches sources
gsettings set org.freedesktop.ibus.engine.hangul disable-latin-mode true    # Hangul is always Korean
gsettings set org.freedesktop.ibus.engine.hangul initial-input-mode 'hangul'
```

Add `grp:toggle` to any `xkb-options` you already have instead of replacing
them.

### Manual install

`setup.sh` wraps `install.sh`, which only installs the engine:

```sh
sudo ./install.sh --layout us    # your keyboard layout; see below
ibus restart                     # as your normal user, not root
```

Then add **LaTeX symbols** as an input source yourself: on GNOME, Settings →
Keyboard → Input Sources → Add → English → LaTeX symbols; elsewhere,
`ibus-setup` → Input Method → Add, or `ibus engine latex`. If `ibus restart`
does not pick it up on GNOME, run
`systemctl --user restart org.freedesktop.IBus.session.GNOME.service`.
Remove it with `sudo ./install.sh --uninstall`.

The files go to `/usr/local/share/ibus-latex` (change with `--prefix`), plus
one engine definition, `latex.xml`, in IBus's own `share/ibus/component`
directory. Root is needed for that file. IBus only reads engine definitions
from there: `IBUS_COMPONENT_PATH` would allow another directory, but the
daemon skips it whenever the system registry cache in `/var/cache/ibus` is
current, as it usually is on Fedora.

`--layout` sets the layout used while the engine is active, e.g.
`--layout gb` or `--layout de+nodeadkeys`. Without it, the installer reuses
the layout of a previous install, or falls back to `default`, which keeps
whatever layout is already active. `default` suits KDE and most non-GNOME
desktops. **GNOME needs an explicit layout**: it switches to the engine's
layout when you select the input source. `setup.sh` works out the layout for
you.

Packagers: `./install.sh --destdir "$pkgdir" --prefix /usr --layout default`
stages the files without root and without touching the running system.

### Try without installing

Run `./ibus-engine-latex` in a terminal and switch to it with
`ibus engine latex-dev`. It lasts until IBus restarts.

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
  installer is plain POSIX `sh` (checked with dash and ShellCheck) and finds
  IBus's directory with pkg-config or from where `ibus-daemon` lives.
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
tests/run-setup-tests.sh                # setup.sh, with stubs and sandboxed settings
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
data/text.tsv            text accents and letters (tools/gen_text_tsv.py)
data/extra.tsv           super/subscripts
data/unicode-math.tsv    generated from unicode-math-table.tex
component/latex.xml.in   IBus engine definition template
setup.sh                 one-command install + desktop setup (POSIX sh)
install.sh               system-wide installer, also for packagers
tools/desktop_setup.py   input-source changes for setup.sh (saved for undo)
```

## License

MIT for the code (see `LICENSE`). `data/unicode-math.tsv` is derived from
`unicode-math-table.tex` in the [unicode-math](https://github.com/latex3/unicode-math)
package, which is distributed under the LaTeX Project Public License 1.3c.
