#!/bin/sh
# Validate the JavaScript the self-test actually serves.
#
# The page is a Python triple-quoted string, so JS escaping has to survive both
# Python and the browser. It did not once: generated onclick handlers contained
# \' , Python collapsed it to a bare quote, the script became invalid and every
# button on the page died at once - with no error visible on the device.
#
# Python's ast.parse cannot see this; it only checks the Python. Run this after
# touching PAGE.
set -e
URL="${1:-http://127.0.0.1:8081/}"
NODE="$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | tail -1)"
[ -n "$NODE" ] && PATH="$NODE:$PATH"
TMP="$(mktemp -t papyrjs).js"
curl -fsS "$URL" | sed -n '/<script>/,/<\/script>/p' | sed '1d;$d' > "$TMP"
node --check "$TMP" && echo "OK  served JavaScript parses ($(wc -c < "$TMP" | tr -d ' ') bytes)"
rm -f "$TMP"
