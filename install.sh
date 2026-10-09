#!/bin/bash
# Installation idempotente d'InfraBackup (aucune dépendance Python : pas de venv)
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# Création du wrapper ~/.local/bin/infrabackup (transmet les arguments)
mkdir -p ~/.local/bin
cat > ~/.local/bin/infrabackup << EOF
#!/bin/bash
exec python3 "$REPO_DIR/infrabackup.py" "\$@"
EOF
chmod +x ~/.local/bin/infrabackup

# Création du lanceur GNOME
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/infrabackup.desktop << EOF
[Desktop Entry]
Name=InfraBackup
Comment=Lance la sauvegarde des configurations
Exec=bash -c '~/.local/bin/infrabackup; read -r -p "Terminé, Entrée pour fermer"'
Icon=drive-harddisk
Terminal=true
Type=Application
Categories=System;
EOF

echo "Installation terminée"
