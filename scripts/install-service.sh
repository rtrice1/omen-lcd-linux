#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --user USER [--source PATH] [--start] [--no-start]" >&2
  exit 2
}

SERVICE_USER=""
SOURCE="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
START=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --user) [ "$#" -ge 2 ] || usage; SERVICE_USER=$2; shift 2 ;;
    --source) [ "$#" -ge 2 ] || usage; SOURCE=$2; shift 2 ;;
    --start) START=1; shift ;;
    --no-start) START=0; shift ;;
    *) usage ;;
  esac
done

[ -n "$SERVICE_USER" ] || { echo "--user is required" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
[ -d "$SOURCE" ] || { echo "source directory not found: $SOURCE" >&2; exit 1; }
[ -f "$SOURCE/pyproject.toml" ] || { echo "source lacks pyproject.toml" >&2; exit 1; }
[ -f "$SOURCE/systemd/omen-lcd.service.in" ] || { echo "service template missing" >&2; exit 1; }
[ -f "$SOURCE/udev/70-omen-lcd.rules" ] || { echo "udev rule missing" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "unknown service user: $SERVICE_USER" >&2; exit 1; }
[ "$(id -u "$SERVICE_USER")" -ne 0 ] || { echo "service user must be nonroot" >&2; exit 1; }

SERVICE_GROUP=$(id -gn "$SERVICE_USER")
if systemctl is-active --quiet omen-lcd.service; then
  systemctl stop omen-lcd.service
fi
groupadd -f omenlcd
INSTALL=/opt/omen-lcd-linux
install -d -m 0755 "$INSTALL"
python3 -m venv "$INSTALL/venv"
"$INSTALL/venv/bin/python" -m pip install "$SOURCE"
install -d -m 0755 "$INSTALL/systemd"
sed -e "s/@SERVICE_USER@/$SERVICE_USER/g" -e "s/@SERVICE_GROUP@/$SERVICE_GROUP/g" \
  "$SOURCE/systemd/omen-lcd.service.in" > "$INSTALL/systemd/omen-lcd.service"
install -m 0644 "$INSTALL/systemd/omen-lcd.service" /etc/systemd/system/omen-lcd.service
install -m 0644 "$SOURCE/udev/70-omen-lcd.rules" /etc/udev/rules.d/70-omen-lcd.rules
systemctl daemon-reload
udevadm control --reload-rules
if [ "$START" -eq 1 ]; then
  systemctl enable --now omen-lcd.service
else
  systemctl disable omen-lcd.service >/dev/null 2>&1 || true
  echo "installed; service not started (use --start after hardware acceptance)"
fi
