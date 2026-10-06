#!/bin/sh
# Install (or uninstall) ibus-latex.  Plain POSIX sh: works with dash, bash,
# busybox ash and the BSD shells.  Run ./install.sh --help for options.
#
# IBus engines have to be installed system-wide: ibus-daemon reads engine
# definitions from its own share/ibus/component directory, and the system
# registry cache some distributions keep (Fedora: /var/cache/ibus) makes it
# ignore IBUS_COMPONENT_PATH, so there is no reliable per-user location.

set -eu
umask 022

NAME=ibus-latex
ENGINE=latex
COMPONENT=org.freedesktop.IBus.Latex

usage() {
	cat <<EOF
Usage: sudo ./install.sh [options]

Options:
  --prefix DIR     where the engine's files go: DIR/share/$NAME
                   (default: /usr/local)
  --layout L[+V]   keyboard layout to use while the engine is active, e.g. us,
                   gb, de+nodeadkeys.  Default: the layout of a previous
                   install, else "default" (keep the current layout).
                   GNOME needs an explicit layout.
  --python PATH    Python 3 interpreter for the engine (default: python3)
  --destdir DIR    stage the files under DIR instead of installing (for
                   packagers); does not need root
  --uninstall      remove an installation made with the same options
  -h, --help       show this help
EOF
}

say() { printf '%s\n' "$*"; }
die() { printf '%s: %s\n' "${0##*/}" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

args=$*
prefix=/usr/local layout='' python='' destdir='' action=install
while [ $# -gt 0 ]; do
	case $1 in
	--prefix=*) prefix=${1#*=} ;;
	--prefix) [ $# -ge 2 ] || die "$1 needs an argument"; prefix=$2; shift ;;
	--layout=*) layout=${1#*=} ;;
	--layout) [ $# -ge 2 ] || die "$1 needs an argument"; layout=$2; shift ;;
	--python=*) python=${1#*=} ;;
	--python) [ $# -ge 2 ] || die "$1 needs an argument"; python=$2; shift ;;
	--destdir=*) destdir=${1#*=} ;;
	--destdir) [ $# -ge 2 ] || die "$1 needs an argument"; destdir=$2; shift ;;
	--uninstall) action=uninstall ;;
	-h | --help) usage; exit 0 ;;
	*) die "unknown option: $1 (see --help)" ;;
	esac
	shift
done

if [ -z "$destdir" ] && [ "$(id -u)" -ne 0 ]; then
	die "needs root to write to IBus's directories; try: sudo $0${args:+ $args}"
fi

src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
dest=$prefix/share/$NAME

# IBus's own component directory.
ibus_component_dir() {
	pc=$(pkg-config --variable=pkgdatadir ibus-1.0 2>/dev/null || :)
	daemon=$(command -v ibus-daemon 2>/dev/null || :)
	base=${daemon%/*}
	base=${base%/*}
	for d in "$pc" "${base:+$base/share/ibus}" \
		/usr/share/ibus /usr/local/share/ibus /usr/pkg/share/ibus /opt/local/share/ibus; do
		if [ -n "$d" ] && [ -d "$d/component" ]; then
			printf '%s\n' "$d/component"
			return 0
		fi
	done
	return 1
}

check_python() {
	python=${python:-$(command -v python3 2>/dev/null || :)}
	[ -n "$python" ] || die "python3 not found; install Python 3 or pass --python"
	[ -z "$destdir" ] || return 0
	if ! "$python" -c 'import gi; gi.require_version("IBus", "1.0"); from gi.repository import IBus' 2>/dev/null; then
		cat >&2 <<EOF
${0##*/}: $python cannot load the IBus GObject bindings.  Install them first:
  Debian, Ubuntu:   sudo apt install python3-gi gir1.2-ibus-1.0
  Fedora, RHEL:     sudo dnf install python3-gobject ibus-libs
  Arch:             sudo pacman -S python-gobject ibus
  openSUSE:         sudo zypper install python3-gobject typelib-1_0-IBus-1_0
  Alpine:           sudo apk add py3-gobject3 ibus
  FreeBSD:          sudo pkg install ibus py311-gobject3  (match your Python version)
EOF
		exit 1
	fi
}

# The layout of a previous install, else "default" (IBus leaves the layout
# alone, which suits desktops other than GNOME).
detect_layout() {
	f=$destdir$compdir/$ENGINE.xml
	if [ -f "$f" ]; then
		l=$(sed -n 's|.*<layout>\(.*\)</layout>.*|\1|p' "$f")
		v=$(sed -n 's|.*<layout_variant>\(.*\)</layout_variant>.*|\1|p' "$f")
		if [ -n "$l" ]; then
			printf '%s%s\n' "$l" "${v:++$v}"
			return
		fi
	fi
	printf 'default\n'
}

xml_escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
sed_escape() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'; }

write_component() {
	case $layout in
	*+*) lay=${layout%%+*} var=${layout#*+} ;;
	*) lay=$layout var='' ;;
	esac
	longname="LaTeX symbols"
	[ "$lay" = default ] || longname="$longname ($layout)"
	version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$src/ibus_latex/__init__.py")
	# ibus-daemon splits <exec> like a shell command line.
	exec_line="'$python' '$dest/ibus-engine-latex'"
	sed -e "s|@EXEC@|$(sed_escape "$(xml_escape "$exec_line")")|" \
		-e "s|@VERSION@|$(sed_escape "$version")|" \
		-e "s|@LAYOUT@|$(sed_escape "$(xml_escape "$lay")")|" \
		-e "s|@VARIANT@|$(sed_escape "$(xml_escape "$var")")|" \
		-e "s|@LONGNAME@|$(sed_escape "$(xml_escape "$longname")")|" \
		"$src/component/$ENGINE.xml.in" >"$destdir$compdir/$ENGINE.xml"
	chmod 644 "$destdir$compdir/$ENGINE.xml"
}

remove_files() {
	case $dest in
	*/"$NAME") rm -rf "$destdir$dest" ;;
	*) die "refusing to remove unexpected path: $dest" ;;
	esac
}

# Distributions that keep a system registry cache refresh it when engine
# packages change; do the same so the cache stays valid (and fast).
refresh_system_cache() {
	[ -z "$destdir" ] || return 0
	if have ibus && [ -f /var/cache/ibus/bus/registry ]; then
		ibus write-cache --system >/dev/null 2>&1 || :
	fi
}

restart_hint() {
	cat <<EOF

Restart IBus as your normal user (not root) to load the change:
  ibus restart
On GNOME, if that does not work:
  systemctl --user restart org.freedesktop.IBus.session.GNOME.service
EOF
}

do_install() {
	check_python
	case $python$dest in *\'*) die "paths containing ' are not supported" ;; esac
	compdir=$(ibus_component_dir) || die "IBus not found (no share/ibus/component directory); install ibus first"
	[ -n "$layout" ] || layout=$(detect_layout)

	[ ! -d "$destdir$dest" ] || remove_files
	mkdir -p "$destdir$dest/ibus_latex" "$destdir$dest/data" "$destdir$compdir"
	cp "$src"/ibus_latex/*.py "$destdir$dest/ibus_latex/"
	cp "$src"/data/*.tsv "$destdir$dest/data/"
	cp "$src/ibus-engine-latex" "$destdir$dest/"
	chmod 755 "$destdir$dest/ibus-engine-latex"
	[ -n "$destdir" ] || "$python" -m compileall -q "$dest/ibus_latex" >/dev/null 2>&1 || :
	write_component
	say "Installed $NAME to $destdir$dest (layout: $layout)"
	say "Engine definition: $destdir$compdir/$ENGINE.xml"
	[ -z "$destdir" ] || return 0

	refresh_system_cache
	restart_hint
	cat <<EOF

Then add "LaTeX symbols" as an input source:
  GNOME:  Settings > Keyboard > Input Sources > Add > English > LaTeX symbols
  Other:  ibus-setup > Input Method > Add, or run: ibus engine $ENGINE
and press Ctrl+Shift+L, type mapsto, and press Space.
EOF
}

do_uninstall() {
	compdir=$(ibus_component_dir || :)
	f=$destdir$compdir/$ENGINE.xml
	if [ -n "$compdir" ] && [ -f "$f" ] && grep -q "$COMPONENT" "$f"; then
		rm -f "$f"
		say "Removed $f"
	fi
	if [ -d "$destdir$dest" ]; then
		remove_files
		say "Removed $destdir$dest"
	fi
	[ -z "$destdir" ] || return 0
	refresh_system_cache
	restart_hint
	say "Remove \"LaTeX symbols\" from your input sources if it is still listed."
}

case $action in
install) do_install ;;
uninstall) do_uninstall ;;
esac
