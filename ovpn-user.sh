#!/bin/bash
# ovpn-user.sh - add/del OpenVPN users in psw-file

FILE="/etc/openvpn/psw-file"
ACTION="$1"
USER="$2"
PASS="$3"

case "$ACTION" in
  add)
    # Remove existing entry if exists
    /usr/bin/sed -i "/^$USER:/d" "$FILE"
    # Add new user
    echo "$USER:$PASS" >> "$FILE"
    ;;
  del)
    # Delete user
    /usr/bin/sed -i "/^$USER:/d" "$FILE"
    ;;
  *)
    echo "Usage: $0 add|del username password"
    exit 1
    ;;
esac
