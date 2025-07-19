# 🚀 ROCK Pi 4B+ Deployment Guide

This guide provides step-by-step instructions to deploy and run the Rock Pi 3399 Provisioning System on ROCK Pi 4B+ hardware with automated startup, WiFi management, and BLE fallback.

## 📋 Prerequisites

- ROCK Pi 4B+ with Ubuntu 20.04+ or Debian 11+
- Python 3.8 or higher
- Root/sudo access
- Network connectivity for initial setup

## 🛠️ Installation

### 1. System Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y \
    python3 python3-pip python3-venv \
    git build-essential \
    bluetooth bluez libbluetooth-dev \
    network-manager \
    systemd \
    gpio-utils \
    i2c-tools \
    python3-dev \
    libffi-dev \
    pkg-config

# Enable and start required services
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager
```

### 2. Application Installation

```bash
# Clone the repository
git clone https://github.com/your-org/rock-pi-3399-provisioning.git
cd rock-pi-3399-provisioning

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the application
pip install -e .

# Run initial setup
./setup-rockpi4b.sh
```

### 3. GPIO Permissions Setup

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Create GPIO udev rules
sudo tee /etc/udev/rules.d/99-gpio.rules << 'EOF'
# GPIO permissions for Rock Pi provisioning system
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", ACTION=="add", RUN+="/bin/chown root:gpio /dev/%k", RUN+="/bin/chmod 0660 /dev/%k"
SUBSYSTEM=="gpio", KERNEL=="gpio*", ACTION=="add", RUN+="/bin/chown root:gpio /sys%p/value", RUN+="/bin/chmod 0660 /sys%p/value"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## ⚙️ Systemd Service Configuration

### 1. Create Service User

```bash
# Create dedicated service user
sudo useradd -r -s /bin/false -d /opt/rockpi-provisioning rockpi-service
sudo usermod -a -G gpio,bluetooth,netdev rockpi-service

# Create service directory
sudo mkdir -p /opt/rockpi-provisioning
sudo chown rockpi-service:rockpi-service /opt/rockpi-provisioning
```

### 2. Install Application Files

```bash
# Copy application to service directory
sudo cp -r . /opt/rockpi-provisioning/app
sudo chown -R rockpi-service:rockpi-service /opt/rockpi-provisioning/app

# Create configuration directory
sudo mkdir -p /etc/rockpi-provisioning
sudo chown rockpi-service:rockpi-service /etc/rockpi-provisioning

# Create logs directory
sudo mkdir -p /var/log/rockpi-provisioning
sudo chown rockpi-service:rockpi-service /var/log/rockpi-provisioning
```

### 3. WiFi Configuration Management

Create WiFi configuration handler:

```bash
sudo tee /opt/rockpi-provisioning/wifi-manager.py << 'EOF'
#!/usr/bin/env python3
"""
WiFi Configuration Manager for Rock Pi 4B+
Handles WiFi credentials storage and connection management
"""

import json
import subprocess
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Configuration paths
WIFI_CONFIG_FILE = "/etc/rockpi-provisioning/wifi-config.json"
RESET_GPIO_PIN = 18  # GPIO pin for reset button

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/rockpi-provisioning/wifi-manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WiFiManager:
    """Manages WiFi configuration and connections"""
    
    def __init__(self):
        self.config_file = Path(WIFI_CONFIG_FILE)
        self.ensure_config_dir()
    
    def ensure_config_dir(self):
        """Ensure configuration directory exists"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
    
    def has_saved_credentials(self) -> bool:
        """Check if WiFi credentials are saved"""
        try:
            if not self.config_file.exists():
                return False
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return bool(config.get('ssid') and config.get('password'))
        except Exception as e:
            logger.error(f"Error checking saved credentials: {e}")
            return False
    
    def save_credentials(self, ssid: str, password: str, security: str = "WPA2") -> bool:
        """Save WiFi credentials securely"""
        try:
            config = {
                'ssid': ssid,
                'password': password,
                'security': security,
                'saved_at': str(datetime.now())
            }
            
            # Save with restricted permissions
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set secure permissions (readable only by service user)
            os.chmod(self.config_file, 0o600)
            logger.info(f"WiFi credentials saved for SSID: {ssid}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving WiFi credentials: {e}")
            return False
    
    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Load saved WiFi credentials"""
        try:
            if not self.config_file.exists():
                return None
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return {
                    'ssid': config.get('ssid'),
                    'password': config.get('password'),
                    'security': config.get('security', 'WPA2')
                }
        except Exception as e:
            logger.error(f"Error loading WiFi credentials: {e}")
            return None
    
    def connect_to_wifi(self, ssid: str, password: str) -> bool:
        """Connect to WiFi using nmcli"""
        try:
            # First, check if connection already exists
            result = subprocess.run([
                'nmcli', 'connection', 'show', ssid
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Connection exists, try to activate it
                logger.info(f"Activating existing connection: {ssid}")
                result = subprocess.run([
                    'nmcli', 'connection', 'up', ssid
                ], capture_output=True, text=True)
            else:
                # Create new connection
                logger.info(f"Creating new WiFi connection: {ssid}")
                result = subprocess.run([
                    'nmcli', 'device', 'wifi', 'connect', ssid,
                    'password', password
                ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully connected to WiFi: {ssid}")
                return True
            else:
                logger.error(f"WiFi connection failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to WiFi: {e}")
            return False
    
    def auto_connect(self) -> bool:
        """Auto-connect using saved credentials"""
        credentials = self.load_credentials()
        if not credentials:
            logger.info("No saved WiFi credentials found")
            return False
        
        return self.connect_to_wifi(
            credentials['ssid'], 
            credentials['password']
        )
    
    def clear_credentials(self) -> bool:
        """Clear saved WiFi credentials"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                logger.info("WiFi credentials cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing credentials: {e}")
            return False
    
    def check_reset_button(self) -> bool:
        """Check if GPIO reset button is pressed"""
        try:
            # This is a simplified GPIO check - adapt for your specific setup
            result = subprocess.run([
                'gpioget', 'gpiochip0', str(RESET_GPIO_PIN)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Button pressed if GPIO reads 0 (assuming pull-up)
                return result.stdout.strip() == '0'
        except Exception as e:
            logger.debug(f"GPIO check failed: {e}")
        
        return False


def main():
    """Main WiFi management logic"""
    wifi_manager = WiFiManager()
    
    # Check for reset button press
    if wifi_manager.check_reset_button():
        logger.info("Reset button pressed - clearing WiFi credentials")
        wifi_manager.clear_credentials()
        return False  # Signal to start BLE mode
    
    # Try to auto-connect
    if wifi_manager.has_saved_credentials():
        logger.info("Found saved WiFi credentials - attempting connection")
        if wifi_manager.auto_connect():
            return True  # Successfully connected
        else:
            logger.warning("Auto-connection failed - will start BLE mode")
    else:
        logger.info("No saved WiFi credentials - will start BLE mode")
    
    return False  # Signal to start BLE mode


if __name__ == "__main__":
    import sys
    from datetime import datetime
    
    success = main()
    sys.exit(0 if success else 1)
EOF

# Make executable
sudo chmod +x /opt/rockpi-provisioning/wifi-manager.py
sudo chown rockpi-service:rockpi-service /opt/rockpi-provisioning/wifi-manager.py
```

### 4. Create Systemd Service

```bash
sudo tee /etc/systemd/system/rockpi-provisioning.service << 'EOF'
[Unit]
Description=Rock Pi 4B+ Provisioning Service
Documentation=https://github.com/your-org/rock-pi-3399-provisioning
After=network.target bluetooth.target
Wants=network.target bluetooth.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=exec
User=rockpi-service
Group=rockpi-service
WorkingDirectory=/opt/rockpi-provisioning/app
Environment=PATH=/opt/rockpi-provisioning/app/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/opt/rockpi-provisioning/app/src
Environment=ROCKPI_CONFIG_DIR=/etc/rockpi-provisioning
Environment=ROCKPI_LOG_DIR=/var/log/rockpi-provisioning

# Pre-start WiFi check
ExecStartPre=/opt/rockpi-provisioning/wifi-manager.py

# Main service command - will start in BLE mode if WiFi fails
ExecStart=/opt/rockpi-provisioning/app/venv/bin/python -m src.application.provisioning_orchestrator

# Restart configuration
Restart=always
RestartSec=10
TimeoutStartSec=30
TimeoutStopSec=30

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/rockpi-provisioning /var/log/rockpi-provisioning /tmp
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

# Resource limits
LimitNOFILE=65536
MemoryMax=512M
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rockpi-provisioning

[Install]
WantedBy=multi-user.target
EOF
```

### 5. Create Pre-Boot Service for Early WiFi Setup

```bash
sudo tee /etc/systemd/system/rockpi-wifi-setup.service << 'EOF'
[Unit]
Description=Rock Pi WiFi Pre-Setup Service
Before=rockpi-provisioning.service
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
User=root
ExecStart=/opt/rockpi-provisioning/wifi-manager.py
RemainAfterExit=true
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF
```

## 🔧 GPIO Reset Button Configuration

### 1. Create GPIO Reset Monitor

```bash
sudo tee /opt/rockpi-provisioning/gpio-reset-monitor.py << 'EOF'
#!/usr/bin/env python3
"""
GPIO Reset Button Monitor for Rock Pi 4B+
Monitors GPIO pin for factory reset trigger
"""

import time
import signal
import sys
import subprocess
import logging
from pathlib import Path

# Configuration
RESET_GPIO_PIN = 18
HOLD_TIME_SECONDS = 5  # Hold button for 5 seconds to trigger reset
CHECK_INTERVAL = 0.1   # Check every 100ms

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/rockpi-provisioning/gpio-monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GPIOResetMonitor:
    """Monitors GPIO reset button"""
    
    def __init__(self):
        self.running = True
        self.button_pressed_time = None
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received")
        self.running = False
    
    def _read_gpio(self) -> bool:
        """Read GPIO pin state"""
        try:
            result = subprocess.run([
                'gpioget', 'gpiochip0', str(RESET_GPIO_PIN)
            ], capture_output=True, text=True, timeout=1)
            
            if result.returncode == 0:
                # Return True if button is pressed (GPIO reads 0 with pull-up)
                return result.stdout.strip() == '0'
        except Exception as e:
            logger.debug(f"GPIO read failed: {e}")
        
        return False
    
    def _trigger_reset(self):
        """Trigger factory reset"""
        logger.info("Factory reset triggered!")
        
        try:
            # Clear WiFi credentials
            subprocess.run([
                '/opt/rockpi-provisioning/wifi-manager.py', '--clear'
            ], check=True)
            
            # Restart the main service to enter BLE mode
            subprocess.run([
                'systemctl', 'restart', 'rockpi-provisioning.service'
            ], check=True)
            
            logger.info("Factory reset completed - service restarted in BLE mode")
            
        except Exception as e:
            logger.error(f"Factory reset failed: {e}")
    
    def monitor(self):
        """Main monitoring loop"""
        logger.info(f"Starting GPIO reset monitor on pin {RESET_GPIO_PIN}")
        
        while self.running:
            try:
                button_pressed = self._read_gpio()
                
                if button_pressed:
                    if self.button_pressed_time is None:
                        # Button just pressed
                        self.button_pressed_time = time.time()
                        logger.debug("Reset button pressed")
                    else:
                        # Button still pressed - check hold time
                        hold_time = time.time() - self.button_pressed_time
                        if hold_time >= HOLD_TIME_SECONDS:
                            self._trigger_reset()
                            # Reset the timer to prevent multiple triggers
                            self.button_pressed_time = None
                else:
                    # Button not pressed
                    if self.button_pressed_time is not None:
                        hold_time = time.time() - self.button_pressed_time
                        logger.debug(f"Reset button released after {hold_time:.1f}s")
                        self.button_pressed_time = None
                
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1)  # Longer delay on error
        
        logger.info("GPIO reset monitor stopped")


if __name__ == "__main__":
    monitor = GPIOResetMonitor()
    monitor.monitor()
EOF

# Make executable
sudo chmod +x /opt/rockpi-provisioning/gpio-reset-monitor.py
sudo chown rockpi-service:rockpi-service /opt/rockpi-provisioning/gpio-reset-monitor.py
```

### 2. Create GPIO Monitor Service

```bash
sudo tee /etc/systemd/system/rockpi-gpio-monitor.service << 'EOF'
[Unit]
Description=Rock Pi GPIO Reset Button Monitor
After=multi-user.target

[Service]
Type=simple
User=rockpi-service
Group=rockpi-service
ExecStart=/opt/rockpi-provisioning/gpio-reset-monitor.py
Restart=always
RestartSec=5
TimeoutStopSec=10

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/rockpi-provisioning
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

## 🚀 Service Activation

### 1. Enable and Start Services

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services for auto-start
sudo systemctl enable rockpi-wifi-setup.service
sudo systemctl enable rockpi-provisioning.service
sudo systemctl enable rockpi-gpio-monitor.service

# Start services
sudo systemctl start rockpi-wifi-setup.service
sudo systemctl start rockpi-provisioning.service
sudo systemctl start rockpi-gpio-monitor.service

# Check service status
sudo systemctl status rockpi-provisioning.service
sudo systemctl status rockpi-gpio-monitor.service
```

### 2. Verify Installation

```bash
# Check service logs
sudo journalctl -u rockpi-provisioning.service -f

# Check WiFi manager logs
sudo tail -f /var/log/rockpi-provisioning/wifi-manager.log

# Check GPIO monitor logs
sudo tail -f /var/log/rockpi-provisioning/gpio-monitor.log

# Test GPIO reset (optional)
sudo /opt/rockpi-provisioning/gpio-reset-monitor.py
```

## 📱 Boot Sequence Behavior

### Normal Boot Process:

1. **System Boot** → NetworkManager starts
2. **WiFi Setup Service** → Checks for saved credentials
3. **If WiFi credentials exist:**
   - Attempts auto-connection using `nmcli`
   - On success: Main service starts in WiFi mode
   - On failure: Main service starts in BLE mode
4. **If no WiFi credentials:**
   - Main service starts in BLE mode
5. **GPIO Monitor** → Continuously monitors reset button

### Reset Button Behavior:

1. **Short press** (< 5 seconds): No action
2. **Long press** (≥ 5 seconds): 
   - Clears saved WiFi credentials
   - Restarts main service in BLE mode
   - Logs factory reset event

## 🔒 Security Configuration

### 1. WiFi Credential Security

```bash
# Ensure secure permissions on config directory
sudo chmod 700 /etc/rockpi-provisioning
sudo chown rockpi-service:rockpi-service /etc/rockpi-provisioning

# WiFi config file will have 600 permissions (owner read/write only)
```

### 2. Service Security

The systemd service includes several security hardening options:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `ProtectSystem=strict` - Read-only filesystem access
- `PrivateTmp=true` - Isolated /tmp directory
- Resource limits (memory, CPU, file handles)

### 3. Log Rotation

```bash
sudo tee /etc/logrotate.d/rockpi-provisioning << 'EOF'
/var/log/rockpi-provisioning/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su rockpi-service rockpi-service
}
EOF
```

## 🛠️ Maintenance Commands

```bash
# View service status
sudo systemctl status rockpi-provisioning.service

# Restart service
sudo systemctl restart rockpi-provisioning.service

# View logs
sudo journalctl -u rockpi-provisioning.service -f

# Manual WiFi reset
sudo /opt/rockpi-provisioning/wifi-manager.py --clear

# Check WiFi status
nmcli device wifi list
nmcli connection show

# Test BLE functionality
bluetoothctl
```

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check service status and logs
sudo systemctl status rockpi-provisioning.service
sudo journalctl -u rockpi-provisioning.service --no-pager

# Check permissions
ls -la /opt/rockpi-provisioning/
ls -la /etc/rockpi-provisioning/

# Test manual start
sudo -u rockpi-service /opt/rockpi-provisioning/app/venv/bin/python -m src.application.provisioning_orchestrator
```

### WiFi Connection Issues
```bash
# Check NetworkManager status
sudo systemctl status NetworkManager

# Reset network connections
sudo nmcli networking off
sudo nmcli networking on

# Manual WiFi connection test
sudo nmcli device wifi connect "SSID" password "PASSWORD"
```

### GPIO Reset Not Working
```bash
# Check GPIO permissions
ls -la /dev/gpiochip*

# Test GPIO manually
gpioget gpiochip0 18

# Check monitor service
sudo systemctl status rockpi-gpio-monitor.service
```

### BLE Not Working
```bash
# Check Bluetooth service
sudo systemctl status bluetooth

# Reset Bluetooth
sudo systemctl restart bluetooth

# Check BLE adapter
bluetoothctl show
```

## 📊 Performance Optimization

### 1. CPU Governor Settings
```bash
# Set performance governor for better responsiveness
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### 2. Memory Optimization
```bash
# Add to /etc/sysctl.conf for memory optimization
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'vm.dirty_ratio=15' | sudo tee -a /etc/sysctl.conf
```

### 3. Network Optimization
```bash
# Optimize network buffer sizes
echo 'net.core.rmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
```

## 🔄 Updates and Maintenance

### Application Updates
```bash
# Stop services
sudo systemctl stop rockpi-provisioning.service

# Update application
cd /opt/rockpi-provisioning/app
sudo -u rockpi-service git pull
sudo -u rockpi-service /opt/rockpi-provisioning/app/venv/bin/pip install -e .

# Restart services
sudo systemctl start rockpi-provisioning.service
```

### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Reboot if kernel updated
sudo reboot
```

This deployment guide ensures your Rock Pi 4B+ provisioning system will:
- ✅ Auto-start on boot
- ✅ Manage WiFi credentials securely
- ✅ Fall back to BLE mode when needed
- ✅ Handle GPIO reset button properly
- ✅ Maintain security and performance
- ✅ Provide comprehensive logging and monitoring