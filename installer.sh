#!/bin/bash
# AeroTUI Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/nebuff/AeroTUI/main/installer.sh | bash

set -e

echo "=== AeroTUI Installer ==="
echo "v1.2 Alpha"
echo "Written by Nebuff"
sleep 1
echo "[!] YOU MUST HAVE A INTERNET CONNECTION AND SUDOERS/ROOT PRIVLEDGES"
sleep 3
echo "[!] Proceeding with Install"

# 1. Update and install dependencies
echo "[+] Installing dependencies..."
if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv sqlite3 tmux git
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip sqlite tmux git
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip sqlite tmux git
else
    echo "Unsupported package manager. Please install python3, pip, sqlite3, and tmux manually."
    exit 1
fi

# 2. Install Python deps (force break-system-packages for Debian/Ubuntu)
echo "[+] Installing Python libraries..."
pip3 install --upgrade pip --break-system-packages
pip3 install textual rich --break-system-packages

# 3. Create Aero system dirs
echo "[+] Creating Aero directories..."
sudo mkdir -p /var/lib/aero_shell
sudo mkdir -p /opt/aero_apps
sudo chmod -R 755 /var/lib/aero_shell /opt/aero_apps

# 4. Copy project code
echo "[+] Installing AeroTUI base..."
sudo mkdir -p /usr/local/share/aero_shell
curl -fsSL https://raw.githubusercontent.com/nebuff/AeroTUI/main/base.py -o /tmp/aero_base.py
sudo cp /tmp/aero_base.py /usr/local/share/aero_shell/aero.py

# 5. Create launcher command
echo "[+] Creating launcher..."
sudo tee /usr/local/bin/aero >/dev/null <<'EOF'
#!/bin/bash
exec python3 /usr/local/share/aero_shell/aero.py "$@"
EOF
sudo chmod +x /usr/local/bin/aero

# 6. Configure tmux branding
echo "[+] Configuring tmux branding..."
sudo tee /etc/tmux.conf >/dev/null <<'EOF'
# Aero TUI Shell tmux config
set -g status-bg colour235
set -g status-fg white
set -g status-left " Aero | #[fg=green]#S #[default]"
set -g status-right "#[fg=cyan]%Y-%m-%d %H:%M #[default]"
EOF

echo "=== Installation Complete ==="
echo "Run 'aero' to start the Aero TUI Shell."
