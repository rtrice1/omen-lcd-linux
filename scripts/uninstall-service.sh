#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
systemctl disable --now omen-lcd.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/omen-lcd.service
rm -f /etc/udev/rules.d/70-omen-lcd.rules
systemctl daemon-reload
udevadm control --reload-rules
rm -rf /opt/omen-lcd-linux
echo "removed only the omen-lcd service unit and /opt/omen-lcd-linux"
