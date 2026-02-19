#!/usr/bin/env bash
# Install ElvAgent as a systemd user service.
#
# Usage:
#   chmod +x scripts/setup_systemd.sh
#   ./scripts/setup_systemd.sh
#
# To uninstall:
#   systemctl --user stop elvagent
#   systemctl --user disable elvagent
#   rm ~/.config/systemd/user/elvagent.service
#   systemctl --user daemon-reload

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="elvagent"
SERVICE_FILE="$SCRIPT_DIR/elvagent.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== ElvAgent systemd service installer ==="

# Verify we're in the right place
if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "ERROR: $SERVICE_FILE not found. Run this script from the project root." >&2
    exit 1
fi

# Verify venv exists
if [[ ! -f "/home/elvern/ElvAgent/.venv/bin/python" ]]; then
    echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -r requirements.txt" >&2
    exit 1
fi

# Create user systemd directory
mkdir -p "$SYSTEMD_DIR"

# Copy service file
cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME.service"
echo "Service file installed: $SYSTEMD_DIR/$SERVICE_NAME.service"

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable (start on login) and start now
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

echo ""
echo "=== Done! ElvAgent is running. ==="
echo ""
echo "Useful commands:"
echo "  Status : systemctl --user status $SERVICE_NAME"
echo "  Logs   : journalctl --user -u $SERVICE_NAME -f"
echo "  Stop   : systemctl --user stop $SERVICE_NAME"
echo "  Restart: systemctl --user restart $SERVICE_NAME"
