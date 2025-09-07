#!/bin/bash
# Aero Installer Script
# This will set up the Aero TUI Shell environment on a minimal Linux install

set -e

echo "=== Aero Installer ==="

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
    echo "Unsupported package manager. Install python3, pip, sqlite3, and tmux manually."
    exit 1
fi

# 2. Install Python deps
echo "[+] Installing Python libraries..."
pip3 install --upgrade pip
pip3 install textual rich

# 3. Create Aero system dirs
echo "[+] Creating Aero directories..."
sudo mkdir -p /var/lib/aero_shell
sudo mkdir -p /opt/aero_apps
sudo chmod -R 755 /var/lib/aero_shell /opt/aero_apps

# 4. Place main Aero script
echo "[+] Installing Aero TUI Shell..."
SCRIPT_PATH="/usr/local/bin/aero"
sudo tee $SCRIPT_PATH >/dev/null <<'EOF'
#!/bin/bash
# Launcher for Aero TUI Shell
exec python3 /usr/local/share/aero_shell/aero.py "$@"
EOF

sudo chmod +x $SCRIPT_PATH

# 5. Copy project code
echo "[+] Copying Aero sources..."
sudo mkdir -p /usr/local/share/aero_shell
# Expect aero.py to be in current directory
sudo cp textual_tui_shell_base.py /usr/local/share/aero_shell/aero.py

# 6. Setup tmux default branding for Aero
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
