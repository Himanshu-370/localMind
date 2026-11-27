#!/bin/sh
set -eu

PACKAGE="${LOCALMIND_PACKAGE:-localmind-graphrag}"

if [ "$(id -u)" -eq 0 ]; then
    echo "LocalMind installs into your user account. Do not run this installer as root or with sudo." >&2
    exit 1
fi

case "$(uname -s)" in
    Darwin|Linux) ;;
    *)
        echo "LocalMind currently supports macOS and Linux." >&2
        exit 1
        ;;
esac

if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
else
    echo "uv is required and will be installed into your user account from astral.sh."
    echo "No administrator access will be used."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [ -x "$HOME/.local/bin/uv" ]; then
        UV="$HOME/.local/bin/uv"
    elif [ -x "$HOME/.cargo/bin/uv" ]; then
        UV="$HOME/.cargo/bin/uv"
    else
        echo "uv was installed but could not be located. Open a new terminal and rerun this command." >&2
        exit 1
    fi
fi

echo "Installing LocalMind as an isolated user tool..."
"$UV" tool install --upgrade "$PACKAGE"

BIN_DIR="$("$UV" tool dir --bin)"
case ":${PATH:-}:" in
    *":$BIN_DIR:"*) PATH_READY=1 ;;
    *) PATH_READY=0 ;;
esac

echo
echo "LocalMind is installed."
if [ "$PATH_READY" -eq 1 ]; then
    echo "Next:"
    echo "  localmind doctor"
    echo "  localmind"
else
    echo "Add LocalMind to this shell with:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    echo
    echo "Then run:"
    echo "  localmind doctor"
    echo "  localmind"
    echo
    echo "Run 'uv tool update-shell' if you want uv to update your shell profile."
fi
