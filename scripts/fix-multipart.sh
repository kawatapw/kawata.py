#!/bin/bash

TARGET_PATH="/srv/root/kawata.py/lib/python3.11/site-packages/multipart/multipart.py"
BACKUP_PATH="${TARGET_PATH}.bak"

# Check if target file exists
if [[ ! -f "$TARGET_PATH" ]]; then
    echo "Error: File not found at $TARGET_PATH"
    exit 1
fi

# Make a backup before modifying
cp "$TARGET_PATH" "$BACKUP_PATH"
echo "Backup saved to $BACKUP_PATH"

# Comment out the two lines causing log spam
sed -i '/if c not in (CR, LF):/s/^/        # /' "$TARGET_PATH"
sed -i '/self.logger.warning("Consuming a byte .* in the end state", c)/s/^/        # /' "$TARGET_PATH"

echo "Patched $TARGET_PATH to disable spammy multipart logs."
