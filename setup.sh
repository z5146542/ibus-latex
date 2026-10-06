#!/bin/sh
# One-command setup: install ibus-latex system-wide (asks for your password
# once) and switch your desktop over to it.  Run as your normal user:
#
#     ./setup.sh
#
# Plain POSIX sh.  ./setup.sh --help lists the options.

set -eu

usage() {
	cat <<EOF
Usage: ./setup.sh [options]

Installs ibus-latex and makes it your English input source.  Missing
dependencies are offered for installation; you are asked for your password
(sudo/doas) for the system-wide part.

Options:
  --layout L[+V]    keyboard layout for the engine (default: detected)
  --add             add "LaTeX symbols" next to your layout instead of
                    replacing it
  --toggle-key KEY  GNOME: make KEY switch input sources, one of
                    ralt lalt rctrl lctrl caps menu hangul.  With Hangul
                    among your sources it also makes Hangul always Korean, so
                    KEY toggles Korean <-> English+LaTeX.  Hangul users are
                    offered their current Korean/English key automatically.
  --no-toggle       do not offer a toggle key
  --yes             do not ask before installing missing packages
  --uninstall       undo everything setup.sh did
  -h, --help        show this help
EOF
}

say() { printf '%s\n' "$*"; }
die() { printf '%s: %s\n' "${0##*/}" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

layout='' add=0 toggle='' offer_toggle=1 yes=0 action=install
while [ $# -gt 0 ]; do
	case $1 in
	--layout=*) layout=${1#*=} ;;
	--layout) [ $# -ge 2 ] || die "$1 needs an argument"; layout=$2; shift ;;
	--add) add=1 ;;
	--toggle-key=*) toggle=${1#*=} ;;
	--toggle-key) [ $# -ge 2 ] || die "$1 needs an argument"; toggle=$2; shift ;;
	--no-toggle) offer_toggle=0 ;;
	--yes | -y) yes=1 ;;
	--uninstall) action=uninstall ;;
	-h | --help) usage; exit 0 ;;
	*) die "unknown option: $1 (see --help)" ;;
	esac
	shift
done

case $toggle in
'' | ralt | lalt | rctrl | lctrl | caps | menu | hangul) ;;
*) die "unknown toggle key: $toggle (see --help)" ;;
esac

[ "$(id -u)" -ne 0 ] || die "run this as your normal user, not root; it asks for your password when needed"

src=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
python=$(command -v python3 2>/dev/null || :)

as_root() {
	if have sudo; then
		sudo "$@"
	elif have doas; then
		doas "$@"
	else
		die "need sudo or doas to install system-wide"
	fi
}

ask() {  # ask "question"  -> true for yes (default yes)
	[ -t 0 ] || return 1
	printf '%s [Y/n] ' "$1"
	read -r answer || return 1
	case $answer in [nN]*) return 1 ;; esac
}

have_deps() {
	[ -n "$python" ] && have ibus-daemon && have ibus &&
		"$python" -c 'import gi; gi.require_version("IBus", "1.0"); from gi.repository import IBus' 2>/dev/null
}

install_deps() {
	if have apt-get; then
		set -- apt-get install -y ibus python3-gi gir1.2-ibus-1.0
	elif have dnf; then
		set -- dnf install -y ibus python3-gobject ibus-libs
	elif have pacman; then
		set -- pacman -S --needed --noconfirm ibus python-gobject
	elif have zypper; then
		set -- zypper --non-interactive install ibus python3-gobject typelib-1_0-IBus-1_0
	elif have apk; then
		set -- apk add ibus py3-gobject3
	elif have xbps-install; then
		set -- xbps-install -y ibus python3-gobject
	elif [ "$(uname -s)" = FreeBSD ] && have pkg; then
		v=$("$python" -c 'import sys; print("%d%d" % sys.version_info[:2])' 2>/dev/null || echo 311)
		set -- pkg install -y ibus "py$v-gobject3"
	else
		die "IBus and Python's GObject bindings for it are missing; install them with your package manager"
	fi
	say "IBus and/or Python's GObject bindings for it are missing."
	if [ "$yes" = 0 ] && ! ask "Install them now ($*)?"; then
		die "not installing dependencies; run: sudo $*"
	fi
	as_root "$@"
	python=$(command -v python3 2>/dev/null || :)
	have_deps || die "dependencies still missing after installing them"
}

ibus_running() {
	have pgrep && pgrep -u "$(id -u)" -x ibus-daemon >/dev/null 2>&1
}

restart_ibus() {
	if have systemctl; then
		for unit in org.freedesktop.IBus.session.GNOME.service org.freedesktop.IBus.session.generic.service; do
			if systemctl --user --quiet is-active "$unit" 2>/dev/null; then
				systemctl --user restart "$unit"
				return 0
			fi
		done
	fi
	if ibus_running; then
		ibus restart >/dev/null 2>&1 && return 0
	fi
	return 1
}

wait_for_engine() {
	i=0
	while [ $i -lt 30 ]; do
		if ibus list-engine 2>/dev/null | grep -q '^ *latex '; then
			return 0
		fi
		sleep 1
		i=$((i + 1))
	done
	return 1
}

helper() { "$python" "$src/tools/desktop_setup.py" "$@"; }

do_install() {
	have_deps || install_deps
	ibus_running || restart_ibus || {
		say "Note: IBus is not running.  Make it your input method, e.g."
		say "  Debian/Ubuntu: im-config -n ibus     KDE: System Settings > Keyboard > Virtual Keyboard > IBus"
		say "then log out and back in.  Continuing with the installation."
	}

	[ -n "$layout" ] || layout=$(helper detect-layout)
	say "Installing ibus-latex (keyboard layout: $layout); you may be asked for your password."
	as_root "$src/install.sh" --layout "$layout" --quiet

	if restart_ibus && wait_for_engine; then
		say "IBus has loaded the engine."
	else
		say "IBus has not picked up the engine yet; log out and back in if it does not appear."
	fi

	if [ -z "$toggle" ] && [ "$offer_toggle" = 1 ]; then
		suggested=$(helper suggest-toggle)
		if [ -n "$suggested" ]; then
			say "You switch Korean/English with '$suggested' inside Hangul.  The LaTeX hotkey"
			say "only works in the LaTeX English source, so '$suggested' can switch between"
			say "Hangul (always Korean) and English+LaTeX instead."
			if ask "Set that up?"; then toggle=$suggested; fi
		fi
	fi

	set --
	[ "$add" = 0 ] || set -- --add
	[ -z "$toggle" ] || set -- "$@" --toggle-key "$toggle"
	helper enable "$@"

	cat <<EOF

Done.  Switch to English (Super+Space${toggle:+ or $toggle}), press Ctrl+Shift+L,
type mapsto, and press Space to get ↦.  Undo everything with: ./setup.sh --uninstall
EOF
}

do_uninstall() {
	[ -n "$python" ] || die "python3 not found"
	helper disable
	as_root "$src/install.sh" --uninstall --quiet
	restart_ibus || :
	say "ibus-latex removed."
}

case $action in
install) do_install ;;
uninstall) do_uninstall ;;
esac
