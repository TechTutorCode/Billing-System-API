#!/bin/bash
# /usr/local/bin/ovpn-user.sh
FILE="/etc/openvpn/psw-file"
ACTION="$1"
USER="$2"
PASS="$3"

case "$ACTION" in
  add)
    # Remove old entry if exists
    sed -i "/^$USER:/d" "$FILE"
    echo "$USER:$PASS" >> "$FILE"
    ;;
  del)
    sed -i "/^$USER:/d" "$FILE"
    ;;
  *)
    echo "Usage: $0 add|del username password"
    exit 1
    ;;
esac
