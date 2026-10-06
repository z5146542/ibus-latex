#!/bin/sh
# End-to-end test: start a private ibus-daemon (own D-Bus session, config and
# cache, so the desktop's IBus is untouched) that runs the engine from this
# source tree, then drive it with tests/ibus_session.py.
# Exits 77 (skipped) if dbus-run-session or ibus-daemon is missing.

set -eu

src=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
python=${PYTHON:-$(command -v python3 || :)}
for tool in dbus-run-session ibus-daemon "$python"; do
	if [ -z "$tool" ] || ! command -v "$tool" >/dev/null 2>&1; then
		echo "skipped: ${tool:-python3} not found"
		exit 77
	fi
done

tmp=$(mktemp -d "${TMPDIR:-/tmp}/ibus-latex-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/component" "$tmp/config" "$tmp/cache" "$tmp/data"

sed -e "s|@EXEC@|'$python' '$src/ibus-engine-latex'|" \
	-e 's|@VERSION@|test|' -e 's|@LAYOUT@|default|' -e 's|@VARIANT@||' \
	-e 's|@LONGNAME@|LaTeX symbols|' \
	"$src/component/latex.xml.in" >"$tmp/component/latex.xml"

XDG_CONFIG_HOME=$tmp/config
XDG_CACHE_HOME=$tmp/cache
XDG_DATA_HOME=$tmp/data
IBUS_COMPONENT_PATH=$tmp/component
IBUS_ADDRESS_FILE=$tmp/address
IBUS_ADDRESS=unix:path=$tmp/ibus.sock
export XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME IBUS_COMPONENT_PATH \
	IBUS_ADDRESS_FILE IBUS_ADDRESS

status=0
# shellcheck disable=SC2016 # expanded by the inner shell
dbus-run-session -- sh -c '
	ibus-daemon --address="$IBUS_ADDRESS" --panel=disable --config=disable \
		--emoji-extension=disable --cache=none >"$1/daemon.log" 2>&1 &
	daemon=$!
	"$2" "$3/tests/ibus_session.py" -v
	status=$?
	kill "$daemon" 2>/dev/null
	wait "$daemon" 2>/dev/null
	exit $status
' sh "$tmp" "$python" "$src" || status=$?

if [ "$status" -ne 0 ] && [ -s "$tmp/daemon.log" ]; then
	echo "--- ibus-daemon log"
	cat "$tmp/daemon.log"
fi
exit "$status"
