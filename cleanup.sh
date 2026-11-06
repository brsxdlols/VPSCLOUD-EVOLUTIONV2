#!/bin/sh
# Maintenance limited to reporting. Rotation belongs to logrotate / Docker.
# Deliberately does not delete WhatsApp messages, images, backups or host logs.
set -eu
printf '[%s] Evolution: estado do armazenamento\n' "$(date -Iseconds)"
df -h /
