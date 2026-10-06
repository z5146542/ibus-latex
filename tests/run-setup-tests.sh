#!/bin/sh
# Test setup.sh without touching the real system: sudo, systemctl and ibus
# are replaced by stubs (install.sh runs with --destdir), and GSettings uses
# GLib's keyfile backend in a temporary directory instead of dconf.
# Needs the GNOME and ibus-hangul GSettings schemas; exits 77 without them.

set -eu

src=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
for schema in org.gnome.desktop.input-sources org.freedesktop.ibus.engine.hangul org.freedesktop.ibus.general; do
	if ! gsettings list-keys "$schema" >/dev/null 2>&1; then
		echo "skipped: GSettings schema $schema not installed"
		exit 77
	fi
done

tmp=$(mktemp -d "${TMPDIR:-/tmp}/ibus-latex-setup.XXXXXX")
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin" "$tmp/stage" "$tmp/config"

cat >"$tmp/bin/sudo" <<EOF
#!/bin/sh
exec "\$@" --destdir '$tmp/stage'
EOF
cat >"$tmp/bin/systemctl" <<'EOF'
#!/bin/sh
exit 0
EOF
cat >"$tmp/bin/ibus" <<'EOF'
#!/bin/sh
[ "${1:-}" = list-engine ] && echo "  latex - LaTeX symbols"
exit 0
EOF
cat >"$tmp/bin/ibus-daemon" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$tmp/bin/"*

PATH=$tmp/bin:$PATH
GSETTINGS_BACKEND=keyfile
XDG_CONFIG_HOME=$tmp/config
XDG_CURRENT_DESKTOP=GNOME
export PATH GSETTINGS_BACKEND XDG_CONFIG_HOME XDG_CURRENT_DESKTOP

failures=0
check() {  # check <description> <expected> <command...>
	desc=$1 expected=$2
	shift 2
	actual=$("$@" 2>&1) || :
	if [ "$actual" = "$expected" ]; then
		echo "ok   $desc"
	else
		echo "FAIL $desc: expected [$expected], got [$actual]"
		failures=$((failures + 1))
	fi
}
get() { gsettings get "$@"; }
# An existing install's layout wins over detection, so skip on such machines.
check_layout() {
	for f in /usr/share/ibus/component/latex.xml /usr/local/share/ibus/component/latex.xml; do
		if [ -f "$f" ]; then
			echo "skip $1 (ibus-latex is installed on this machine)"
			return
		fi
	done
	check "$1" "$2" python3 "$src/tools/desktop_setup.py" detect-layout
}
setup() { "$src/setup.sh" "$@" </dev/null >"$tmp/out" 2>&1 || { cat "$tmp/out"; return 1; }; }

src_schema=org.gnome.desktop.input-sources
hangul=org.freedesktop.ibus.engine.hangul
gsettings set $src_schema sources "[('ibus', 'hangul'), ('xkb', 'au')]"
gsettings set $src_schema xkb-options "['lv3:rwin_switch']"
gsettings set $hangul switch-keys 'Alt_R'
gsettings set $hangul disable-latin-mode false
gsettings set $hangul initial-input-mode 'latin'

echo "# GNOME with Hangul"
check "suggests the Hangul switch key" "ralt" python3 "$src/tools/desktop_setup.py" suggest-toggle
check_layout "detects the GNOME layout" "au"
setup --layout au --toggle-key ralt
check "engine staged" "yes" sh -c "[ -f '$tmp/stage/usr/local/share/ibus-latex/ibus-engine-latex' ] && echo yes"
check "replaces the layout" "[('ibus', 'hangul'), ('ibus', 'latex')]" get $src_schema sources
check "adds the toggle" "['lv3:rwin_switch', 'grp:toggle']" get $src_schema xkb-options
check "Hangul always Korean" "true" get $hangul disable-latin-mode
check "Hangul starts Korean" "'hangul'" get $hangul initial-input-mode
setup --layout au --toggle-key ralt
check "second run changes nothing" "[('ibus', 'hangul'), ('ibus', 'latex')]" get $src_schema sources
setup --uninstall
check "uninstall restores sources" "[('ibus', 'hangul'), ('xkb', 'au')]" get $src_schema sources
check "uninstall restores options" "['lv3:rwin_switch']" get $src_schema xkb-options
check "uninstall restores Hangul" "false 'latin'" sh -c "echo \$(gsettings get $hangul disable-latin-mode) \$(gsettings get $hangul initial-input-mode)"
check "uninstall removes files" "gone" sh -c "[ ! -e '$tmp/stage/usr/local/share/ibus-latex' ] && echo gone"
check "uninstall removes state" "gone" sh -c "[ ! -e '$tmp/config/ibus-latex/setup-state.json' ] && echo gone"

echo "# GNOME, --add"
gsettings set $src_schema sources "[('xkb', 'us')]"
setup --layout us --add
check "adds beside the layout" "[('xkb', 'us'), ('ibus', 'latex')]" get $src_schema sources
setup --uninstall
check "uninstall removes it" "[('xkb', 'us')]" get $src_schema sources

echo "# other desktops (IBus panel)"
XDG_CURRENT_DESKTOP=KDE
gsettings set org.freedesktop.ibus.general preload-engines "['xkb:us::eng', 'hangul']"
check_layout "layout is left to the desktop" "default"
setup --layout default
check "replaces the xkb engine" "['latex', 'hangul']" get org.freedesktop.ibus.general preload-engines
setup --uninstall
check "uninstall restores engines" "['xkb:us::eng', 'hangul']" get org.freedesktop.ibus.general preload-engines

if [ "$failures" -ne 0 ]; then
	echo "$failures check(s) failed"
	exit 1
fi
echo "all checks passed"
