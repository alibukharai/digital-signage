#!/bin/bash

# Rock Pi 3399 Provisioning System Installation Script

set -e

echo "Installing Rock Pi 3399 Provisioning System..."

# Update system packages
echo "Updating system packages..."
sudo apt update

# Install required system packages
echo "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    bluetooth \
    bluez \
    bluez-tools \
    libbluetooth-dev \
    libglib2.0-dev \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    python3-opencv \
    fonts-dejavu-core \
    wpasupplicant \
    dhcpcd5 \
    wireless-tools \
    net-tools

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/rock-provisioning.service > /dev/null << EOF
[Unit]
Description=Rock Pi 3399 Network Provisioning Service
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$(pwd)/venv/bin/python -m src
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create udev rule for automatic startup
echo "Creating udev rule..."
sudo tee /etc/udev/rules.d/99-rock-provisioning.rules > /dev/null << EOF
# Start provisioning service when no network is available
ACTION=="add", SUBSYSTEM=="net", KERNEL=="wlan0", RUN+="/bin/systemctl start rock-provisioning.service"
EOF

# Enable and start the service
echo "Enabling and starting the service..."
sudo systemctl daemon-reload
sudo systemctl enable rock-provisioning.service

# Create desktop shortcut for manual execution
echo "Creating desktop shortcut..."
mkdir -p ~/Desktop
tee ~/Desktop/rock-provisioning.desktop > /dev/null << EOF
[Desktop Entry]
Name=Rock Pi Provisioning
Comment=Start network provisioning manually
Exec=sudo $(pwd)/venv/bin/python -m src
Icon=network-wireless
Terminal=true
Type=Application
Categories=Network;
EOF

chmod +x ~/Desktop/rock-provisioning.desktop

# Set permissions for Bluetooth access
echo "Setting up Bluetooth permissions..."
sudo usermod -a -G bluetooth $USER

# Create configuration directory
sudo mkdir -p /etc/rockpi-provisioning
sudo chown $USER:$USER /etc/rockpi-provisioning

# Create logs directory
mkdir -p logs

echo ""
echo "Installation completed!"
echo ""
echo "To start the provisioning service manually:"
echo "  sudo systemctl start rock-provisioning.service"
echo ""
echo "To stop the provisioning service:"
echo "  sudo systemctl stop rock-provisioning.service"
echo ""
echo "To view service logs:"
echo "  sudo journalctl -u rock-provisioning.service -f"
echo ""
echo "The service will automatically start when the device boots"
echo "and no network connection is available."
echo ""
echo "Please reboot the system to complete the installation."
