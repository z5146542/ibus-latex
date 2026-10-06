#!/bin/sh
# Install (or uninstall) ibus-latex for the current user or system-wide.
# Plain POSIX sh: works with dash, bash, busybox ash and the BSD shells.
# Run ./install.sh --help for options.

set -eu
umask 022

NAME=ibus-latex
ENGINE=latex
COMPONENT=org.freedesktop.IBus.Latex
SYSTEMD_IBUS_UNITS="org.freedesktop.IBus.session.GNOME.service org.freedesktop.IBus.session.generic.service"

usage() {
	cat <<EOF
Usage: ./install.sh [options]

Options:
  --user           install for the current user (default unless run as root)
  --system         install for all users (needs root)
  --prefix DIR     installation prefix (default: ~/.local for --user,
                   /usr/local for --system); files go to DIR/share/$NAME
  --layout L[+V]   keyboard layout to use while the engine is active, e.g. us,
                   gb, de+nodeadkeys.  Default: the layout of a previous
                   install, else GNOME's first keyboard layout, else "default"
                   (leave the current layout alone).
  --python PATH    Python 3 interpreter for the engine (default: python3)
  --no-restart     do not restart IBus afterwards
  --uninstall      remove an installation made with the same options
  -h, --help       show this help
EOF
}

say() { printf '%s\n' "$*"; }
die() { printf '%s: %s\n' "${0##*/}" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

mode='' prefix='' layout='' python='' restart=1 action=install
while [ $# -gt 0 ]; do
	case $1 in
	--user) mode=user ;;
	--system) mode=system ;;
	--prefix=*) prefix=${1#*=} ;;
	--prefix) [ $# -ge 2 ] || die "$1 needs an argument"; prefix=$2; shift ;;
	--layout=*) layout=${1#*=} ;;
	--layout) [ $# -ge 2 ] || die "$1 needs an argument"; layout=$2; shift ;;
	--python=*) python=${1#*=} ;;
	--python) [ $# -ge 2 ] || die "$1 needs an argument"; python=$2; shift ;;
	--no-restart) restart=0 ;;
	--uninstall) action=uninstall ;;
	-h | --help) usage; exit 0 ;;
	*) die "unknown option: $1 (see --help)" ;;
	esac
	shift
done

if [ -z "$mode" ]; then
	if [ "$(id -u)" -eq 0 ]; then mode=system; else mode=user; fi
fi
if [ "$mode" = system ] && [ "$(id -u)" -ne 0 ]; then
	die "--system needs root; try: sudo $0 --system"
fi

src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

if [ -n "$prefix" ]; then
	datadir=$prefix/share
elif [ "$mode" = user ]; then
	datadir=${XDG_DATA_HOME:-$HOME/.local/share}
else
	datadir=/usr/local/share
fi
dest=$datadir/$NAME
envd=${XDG_CONFIG_HOME:-$HOME/.config}/environment.d
envconf=$envd/60-$NAME.conf

# IBus only reads engine definitions from its own share/ibus/component
# directory, or from the directories listed in $IBUS_COMPONENT_PATH.
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

have_systemd_user() {
	have systemctl && systemctl --user show-environment >/dev/null 2>&1
}

check_python() {
	python=${python:-$(command -v python3 2>/dev/null || :)}
	[ -n "$python" ] || die "python3 not found; install Python 3 or pass --python"
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

# The engine's layout: --layout, else a previous install's, else GNOME's
# first xkb input source, else "default" (IBus leaves the layout alone).
detect_layout() {
	if [ -f "$compdir/$ENGINE.xml" ]; then
		l=$(sed -n 's|.*<layout>\(.*\)</layout>.*|\1|p' "$compdir/$ENGINE.xml")
		v=$(sed -n 's|.*<layout_variant>\(.*\)</layout_variant>.*|\1|p' "$compdir/$ENGINE.xml")
		if [ -n "$l" ]; then
			printf '%s%s\n' "$l" "${v:++$v}"
			return
		fi
	fi
	if [ "$mode" = user ] && have gsettings; then
		l=$(gsettings get org.gnome.desktop.input-sources sources 2>/dev/null |
			tr ')' '\n' | sed -n "s/.*'xkb', '\([^']*\)'.*/\1/p" | head -n 1)
		if [ -n "$l" ]; then
			printf '%s\n' "$l"
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
	*) lay=$layout var= ;;
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
		"$src/component/$ENGINE.xml.in" >"$compdir/$ENGINE.xml"
	chmod 644 "$compdir/$ENGINE.xml"
}

remove_files() {
	case $dest in
	*/"$NAME") rm -rf "$dest" ;;
	*) die "refusing to remove unexpected path: $dest" ;;
	esac
}

ibus_running() {
	have pgrep && pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1
}

restart_ibus() {
	[ "$restart" = 1 ] || return 0
	if [ "$mode" = system ]; then
		say "Now run 'ibus restart' as your normal user (or log out and back in)."
		return 0
	fi
	if have_systemd_user; then
		for unit in $SYSTEMD_IBUS_UNITS; do
			if systemctl --user --quiet is-active "$unit"; then
				systemctl --user restart "$unit"
				say "Restarted IBus ($unit)."
				return 0
			fi
		done
	fi
	if ibus_running; then
		say "IBus was not started by systemd, so it does not see the new"
		say "IBUS_COMPONENT_PATH yet.  Log out and back in, or restart it by hand:"
		say "  . '$dest/env.sh' && ibus-daemon -drx --replace"
	fi
}

# Per-user installs point $IBUS_COMPONENT_PATH at IBus's own directory plus
# ours.  systemd sessions (GNOME, KDE, ...) read environment.d; other setups
# need env.sh sourced from the login profile.
setup_user_env() {
	value=$sys_compdir:$compdir
	cat >"$dest/env.sh" <<EOF
# Lets ibus-daemon find ibus-latex.  Source this from ~/.profile (or the file
# your session reads at login) if your desktop does not use systemd.
IBUS_COMPONENT_PATH='$value'
export IBUS_COMPONENT_PATH
EOF
	if have_systemd_user; then
		mkdir -p "$envd"
		printf 'IBUS_COMPONENT_PATH=%s\n' "$value" >"$envconf"
		systemctl --user set-environment "IBUS_COMPONENT_PATH=$value"
		say "Wrote $envconf"
	else
		say "No systemd user session found.  Add this line to ~/.profile and log in again:"
		say "  . '$dest/env.sh'"
	fi
}

do_install() {
	check_python
	case $python$dest in *\'*) die "paths containing ' are not supported" ;; esac
	sys_compdir=$(ibus_component_dir) || die "IBus not found (no share/ibus/component directory); install ibus first"
	if [ "$mode" = system ]; then compdir=$sys_compdir; else compdir=$dest/component; fi
	[ -n "$layout" ] || layout=$(detect_layout)

	[ ! -d "$dest" ] || remove_files
	mkdir -p "$dest/ibus_latex" "$dest/data" "$compdir"
	cp "$src"/ibus_latex/*.py "$dest/ibus_latex/"
	cp "$src"/data/*.tsv "$dest/data/"
	cp "$src/ibus-engine-latex" "$dest/"
	chmod 755 "$dest/ibus-engine-latex"
	"$python" -m compileall -q "$dest/ibus_latex" >/dev/null 2>&1 || :
	write_component
	say "Installed $NAME to $dest (layout: $layout)"
	say "Engine definition: $compdir/$ENGINE.xml"

	[ "$mode" = system ] || setup_user_env
	restart_ibus
	cat <<EOF

Next: add "LaTeX symbols" as an input source.
  GNOME:  Settings > Keyboard > Input Sources > Add > English > LaTeX symbols
  Other:  ibus-setup > Input Method > Add, or run: ibus engine $ENGINE
Then press Ctrl+Shift+L, type mapsto, and press Space.
EOF
}

do_uninstall() {
	sys_compdir=$(ibus_component_dir || :)
	if [ "$mode" = system ]; then
		f=$sys_compdir/$ENGINE.xml
		if [ -n "$sys_compdir" ] && [ -f "$f" ] && grep -q "$COMPONENT" "$f"; then
			rm -f "$f"
			say "Removed $f"
		fi
	else
		rm -f "$envconf"
		if have_systemd_user; then
			systemctl --user unset-environment IBUS_COMPONENT_PATH
		fi
	fi
	if [ -d "$dest" ]; then
		remove_files
		say "Removed $dest"
	fi
	restart_ibus
	say "Remove \"LaTeX symbols\" from your input sources if it is still listed."
	if [ "$mode" = user ]; then
		say "If you added '. $dest/env.sh' to a profile, remove that line too."
	fi
}

case $action in
install) do_install ;;
uninstall) do_uninstall ;;
esac
