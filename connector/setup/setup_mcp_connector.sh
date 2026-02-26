#!/usr/bin/env bash
# =============================================================================
# simple-legal-doc MCP Connector Setup
# macOS / Linux
#
# Writes the MCP server configuration into the Claude Desktop config file
# at the correct platform-specific path. Uses Python (required by the
# connector itself) for JSON manipulation to avoid jq as a dependency.
# =============================================================================
set -euo pipefail

echo "=========================================="
echo "simple-legal-doc MCP Connector Setup"
echo "=========================================="
echo

# ---------------------------------------------------------------------------
# Resolve platform-specific Claude Desktop config path
# ---------------------------------------------------------------------------
OS="$(uname -s)"

if [ "$OS" = "Darwin" ]; then
    CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
elif [ "$OS" = "Linux" ]; then
    CLAUDE_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude"
else
    echo "ERROR: Unsupported platform: $OS"
    exit 1
fi

CLAUDE_DESKTOP_CONFIG="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

echo "Platform:    $OS"
echo "Config path: $CLAUDE_DESKTOP_CONFIG"
echo

# ---------------------------------------------------------------------------
# Collect required paths interactively
# ---------------------------------------------------------------------------
read -rp "Absolute path to mcp_server.py: " CONNECTOR_PATH
read -rp "Absolute path to python3 executable: " PYTHON_PATH

# Validate inputs
if [ ! -f "$CONNECTOR_PATH" ]; then
    echo "WARNING: mcp_server.py not found at: $CONNECTOR_PATH"
    echo "Proceeding — ensure the path is correct before launching Claude Desktop."
fi

if [ ! -x "$PYTHON_PATH" ]; then
    echo "WARNING: Python executable not found or not executable at: $PYTHON_PATH"
    echo "Proceeding — ensure the path is correct before launching Claude Desktop."
fi

WORKSPACE_DIR="$HOME/Downloads"

# ---------------------------------------------------------------------------
# Ensure config directory exists
# ---------------------------------------------------------------------------
mkdir -p "$CLAUDE_CONFIG_DIR"

# ---------------------------------------------------------------------------
# Write or update claude_desktop_config.json
#
# Uses Python for JSON manipulation — jq is not assumed to be present.
# The script merges the new mcpServers entry into any existing config
# rather than overwriting the entire file.
# ---------------------------------------------------------------------------
python3 - <<PYEOF
import json
import os
import sys

config_path = "$CLAUDE_DESKTOP_CONFIG"
connector_path = "$CONNECTOR_PATH"
python_path = "$PYTHON_PATH"
workspace = "$WORKSPACE_DIR"

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"WARNING: Existing config is malformed ({exc}). Starting fresh.")
            config = {}
else:
    config = {}

config.setdefault("mcpServers", {})
config["mcpServers"]["simple-legal-doc"] = {
    "command": python_path,
    "args": [connector_path],
    "env": {
        "BACKEND_URL": "http://localhost:8000",
        "AUDITOR_URL": "http://localhost:8001",
        "WORKSPACE_DIR": workspace,
        "X402_ENABLED": "false",
    },
}

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
    f.write("\n")

print(f"Configuration written to: {config_path}")
PYEOF

echo
echo "=========================================="
echo "Setup complete."
echo
echo "Next steps:"
echo "  1. Start the backend stack:  docker compose up"
echo "  2. Run validation suite:     ./connector/setup/validate_backend.sh"
echo "  3. Launch Claude Desktop."
echo "  4. Ask Claude: 'List available templates.'"
echo
echo "Set X402_ENABLED=true in the config only after the wallet"
echo "signing stub in payments.py is replaced with a real signer."
echo "=========================================="