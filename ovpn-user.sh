#!/bin/bash
# /usr/local/bin/ovpn-user.sh
FILE="/etc/openvpn/psw-file"
ACTION="$1"
USER="$2"
PASS="$3"

# Ensure file exists
if [ ! -f "$FILE" ]; then
    touch "$FILE"
    chmod 600 "$FILE"
fi

case "$ACTION" in
  add)
    if [ -z "$USER" ] || [ -z "$PASS" ]; then
        echo "Error: Username and password are required for add action"
        exit 1
    fi
    # Remove old entry if exists
    sed -i "/^$USER:/d" "$FILE" 2>/dev/null
    echo "$USER:$PASS" >> "$FILE"
    echo "User $USER added successfully"
    ;;
  del)
    if [ -z "$USER" ]; then
        echo "Error: Username is required for del action"
        exit 1
    fi
    # Remove user entry
    if sed -i "/^$USER:/d" "$FILE" 2>/dev/null; then
        echo "User $USER deleted successfully"
    else
        echo "User $USER not found or already deleted"
        exit 0
    fi
    ;;
  *)
    echo "Usage: $0 add|del username password"
    exit 1
    ;;
esac
