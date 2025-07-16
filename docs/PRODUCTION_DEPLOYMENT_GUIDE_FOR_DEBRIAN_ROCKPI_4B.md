# Production Deployment Guide for ROCK Pi 4B+ Digital Signage System

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Licensing Requirements](#licensing-requirements)
3. [Operating System Recommendations](#operating-system-recommendations)
4. [Production Configuration](#production-configuration)
5. [Security Considerations](#security-considerations)
6. [Deployment Strategy](#deployment-strategy)
7. [Compliance & Legal Considerations](#compliance--legal-considerations)
8. [Support & Maintenance](#support--maintenance)

## Executive Summary

This document provides comprehensive guidance for deploying the ROCK Pi 4B+ Digital Signage Provisioning System in production environments. It covers licensing requirements, operating system selection, security considerations, and compliance requirements for commercial deployments.

**Key Recommendations:**
- ✅ **OS Choice**: Radxa Debian 11 (Latest LTS) for production stability
- ✅ **License**: MIT License allows commercial use with minimal restrictions
- ✅ **Dependencies**: All open-source with commercial-friendly licenses
- ✅ **Support**: Long-term support until 2029 from Radxa

## Licensing Requirements

### Current Project License

**License**: MIT License (OSI Approved)
**Commercial Use**: ✅ **ALLOWED**
**Modification**: ✅ **ALLOWED**
**Distribution**: ✅ **ALLOWED**
**Private Use**: ✅ **ALLOWED**
**Patent Grant**: ❌ **NOT PROVIDED**

#### MIT License Summary
```
Copyright (c) 2025 Rock Pi 3399 Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

### Dependency License Analysis

#### ✅ Commercial-Friendly Dependencies

| Package | License | Commercial Use | Notes |
|---------|---------|----------------|-------|
| **bleak** | MIT | ✅ Yes | Bluetooth Low Energy library |
| **cryptography** | Apache 2.0/BSD | ✅ Yes | Encryption and security |
| **qrcode** | BSD | ✅ Yes | QR code generation |
| **Pillow** | PIL License (BSD-like) | ✅ Yes | Image processing |
| **opencv-python-headless** | Apache 2.0 | ✅ Yes | Computer vision |
| **numpy** | BSD | ✅ Yes | Numerical computing |
| **psutil** | BSD | ✅ Yes | System monitoring |
| **asyncio-mqtt** | BSD | ✅ Yes | MQTT communication |
| **pydantic** | MIT | ✅ Yes | Data validation |
| **loguru** | MIT | ✅ Yes | Logging |

#### 🔍 License Compatibility Matrix

```
MIT (This Project) ←→ MIT (Dependencies) = ✅ COMPATIBLE
MIT (This Project) ←→ BSD (Dependencies) = ✅ COMPATIBLE
MIT (This Project) ←→ Apache 2.0 (Dependencies) = ✅ COMPATIBLE
```

**Result**: All dependencies are compatible with commercial production use.

### Production License Requirements

#### For Commercial Deployment:

1. **✅ NO License Fees Required**
   - MIT license allows free commercial use
   - No royalties or licensing fees to pay

2. **✅ NO Source Code Disclosure Required**
   - Can deploy without sharing modifications
   - Proprietary additions allowed

3. **⚠️ Attribution Required**
   - Must include MIT license notice in distributions
   - Copyright notices must be preserved

4. **⚠️ Warranty Disclaimer**
   - Software provided "AS IS" without warranty
   - Production deployments should include proper support contracts

#### Recommended License Actions:

```bash
# 1. Create proper LICENSE file
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2025 Rock Pi 3399 Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

# 2. Generate dependency licenses report
pip-licenses --format=markdown --output-file=LICENSES_DEPENDENCIES.md
```

## Operating System Recommendations

### Recommended: Radxa Debian 11 (Production LTS)

#### Why Debian 11 for Production?

**✅ Stability & Long-Term Support**
- Long Term Support (LTS) until 2029
- Security updates guaranteed
- Stable package versions
- Tested hardware compatibility

**✅ Hardware Optimization**
- Official ROCK Pi 4B+ support by Radxa
- OP1 processor optimizations included
- Proper GPU (Mali-T860MP4) drivers
- Bluetooth 5.0 support out-of-the-box

**✅ Production Features**
- SystemD service management
- Professional logging infrastructure
- Enterprise-grade security
- Package management stability

#### Official Debian 11 Images for ROCK Pi 4B+

```bash
# Download URLs (as of July 2025)
# Official Images from: https://wiki.radxa.com/Rock4/downloads

# ROCK 4B+ Latest Images:
DEBIAN_11_DESKTOP="rock-4b-plus-debian-11-desktop-20230315.img.xz"
DEBIAN_11_SERVER="rock-4b-plus-debian-11-server-20230315.img.xz"

# Download from official sources:
wget https://dl.radxa.com/rockpi4/images/debian/${DEBIAN_11_DESKTOP}
wget https://dl.radxa.com/rockpi4/images/debian/${DEBIAN_11_SERVER}
```

#### Default Credentials
```
Username: rock
Password: rock

# Or alternative:
Username: radxa
Password: radxa

# Root access:
sudo su  # No password required for sudo users
```

### Alternative Options

#### Ubuntu 20.04 LTS Server
**Use Case**: If Ubuntu ecosystem required
- LTS support until 2025
- Good ARM64 support
- Large community
- ⚠️ Less optimized for ROCK Pi 4B+ than Debian

#### Custom Buildroot/Yocto
**Use Case**: Minimal embedded deployment
- Reduced attack surface
- Faster boot times
- Custom optimization
- ⚠️ Requires embedded Linux expertise

### Production OS Installation Process

#### 1. Image Preparation
```bash
#!/bin/bash
# Production OS Setup Script for ROCK Pi 4B+

set -euo pipefail

# Configuration
DEBIAN_IMAGE="rock-4b-plus-debian-11-server-20230315.img.xz"
DOWNLOAD_URL="https://dl.radxa.com/rockpi4/images/debian/"
TARGET_DEVICE="/dev/sdX"  # Replace with actual device

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Download and verify image
download_image() {
    log "Downloading Debian 11 for ROCK Pi 4B+..."

    if [[ ! -f "$DEBIAN_IMAGE" ]]; then
        wget "${DOWNLOAD_URL}${DEBIAN_IMAGE}"
        wget "${DOWNLOAD_URL}${DEBIAN_IMAGE}.sha256sum"

        # Verify checksum
        sha256sum -c "${DEBIAN_IMAGE}.sha256sum"
        log "Image verification successful"
    fi
}

# Flash image to storage
flash_image() {
    log "Flashing image to $TARGET_DEVICE..."

    # Ensure device is unmounted
    sudo umount ${TARGET_DEVICE}* 2>/dev/null || true

    # Flash image
    xz -dc "$DEBIAN_IMAGE" | sudo dd of="$TARGET_DEVICE" bs=4M status=progress conv=fsync

    # Sync and notify
    sync
    log "Image flashed successfully"
}

# Main execution
main() {
    download_image
    flash_image
    log "Ready for first boot setup"
}

main "$@"
```

#### 2. First Boot Production Setup
```bash
#!/bin/bash
# First boot production hardening script

# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    git curl wget unzip \
    build-essential \
    python3.10 python3-pip python3-venv \
    bluetooth bluez bluez-tools \
    wireless-tools wpasupplicant \
    systemd htop iotop \
    ufw fail2ban \
    rockchip-multimedia-config

# Create production user
sudo useradd -m -s /bin/bash production
sudo usermod -aG sudo,bluetooth,gpio production

# SSH hardening
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Firewall setup
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh

# Hardware optimizations for OP1
echo 'ondemand' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo 10 | sudo tee /proc/sys/vm/swappiness

log "Production system setup complete"
```

## Production Configuration

### Hardware-Specific Optimizations

#### /boot/hw_intfc.conf Optimization
```bash
# ROCK Pi 4B+ Production Configuration
# File: /boot/hw_intfc.conf

# Enable required interfaces
intfc:i2c7=on          # For GPIO expansion
intfc:uart2=off        # Disable if not needed for security
intfc:uart4=off        # Disable if not needed
intfc:spi1=off         # Disable if not needed
intfc:pwm0=on          # For fan control
intfc:pwm1=on          # For status LEDs

# Performance optimizations
intfc:dtoverlay=pcie-gen2     # Enable PCIe Gen2 for NVMe
intfc:dtoverlay=cpu-opa1      # OP1 CPU optimizations

# Security hardening
#intfc:dtoverlay=console-on-ttyS2  # Disable debug console
```

#### SystemD Service Configuration
```ini
# /etc/systemd/system/rockpi-provisioning.service
[Unit]
Description=ROCK Pi 4B+ Digital Signage Provisioning Service
After=network.target bluetooth.target
Wants=network.target bluetooth.target
StartLimitIntervalSec=30
StartLimitBurst=3

[Service]
Type=exec
User=production
Group=production
WorkingDirectory=/opt/rockpi-provisioning
ExecStart=/opt/rockpi-provisioning/venv/bin/python -m src
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONPATH=/opt/rockpi-provisioning
Environment=ROCKPI_ENV=production

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/rockpi-provisioning/logs
ReadWritePaths=/opt/rockpi-provisioning/config

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
```

### Production Environment Variables
```bash
# /opt/rockpi-provisioning/.env
ROCKPI_ENV=production
ROCKPI_LOG_LEVEL=INFO
ROCKPI_CONFIG_PATH=/opt/rockpi-provisioning/config/production.json
ROCKPI_SECURE_STORAGE=/opt/rockpi-provisioning/secure
ROCKPI_MONITORING_ENABLED=true
ROCKPI_HARDWARE_PLATFORM=rock-pi-4b-plus
```

## Security Considerations

### Production Security Checklist

#### ✅ System Hardening
- [ ] Disable root login
- [ ] SSH key-only authentication
- [ ] Firewall (UFW) configured
- [ ] Fail2ban enabled
- [ ] Non-standard SSH port
- [ ] Regular security updates

#### ✅ Application Security
- [ ] Secure credential storage
- [ ] Encrypted configuration files
- [ ] Rate limiting on BLE connections
- [ ] Input validation on all interfaces
- [ ] Audit logging enabled

#### ✅ Network Security
- [ ] WPA3 support for WiFi
- [ ] Certificate-based authentication
- [ ] VPN support for remote management
- [ ] Network segmentation

### Security Implementation

#### Secure Storage Setup
```bash
#!/bin/bash
# Setup secure storage for production credentials

# Create secure directory
sudo mkdir -p /opt/rockpi-provisioning/secure
sudo chown production:production /opt/rockpi-provisioning/secure
sudo chmod 700 /opt/rockpi-provisioning/secure

# Setup encrypted storage for secrets
sudo apt install -y cryptsetup

# Create encrypted volume for sensitive data
sudo dd if=/dev/urandom of=/opt/rockpi-provisioning/secrets.enc bs=1M count=10
sudo cryptsetup luksFormat /opt/rockpi-provisioning/secrets.enc
sudo cryptsetup luksOpen /opt/rockpi-provisioning/secrets.enc rockpi-secrets
sudo mkfs.ext4 /dev/mapper/rockpi-secrets
sudo mkdir -p /opt/rockpi-provisioning/secrets
sudo mount /dev/mapper/rockpi-secrets /opt/rockpi-provisioning/secrets
sudo chown production:production /opt/rockpi-provisioning/secrets
```

#### Production Firewall Rules
```bash
#!/bin/bash
# Production firewall configuration

# Reset UFW
sudo ufw --force reset

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (change port in production)
sudo ufw allow 22022/tcp comment 'SSH'

# HTTP/HTTPS for management interface
sudo ufw allow 80/tcp comment 'HTTP Management'
sudo ufw allow 443/tcp comment 'HTTPS Management'

# Bluetooth (if remote management needed)
# sudo ufw allow 19001:19999/tcp comment 'Bluetooth Management'

# Monitoring
sudo ufw allow 9090/tcp comment 'Prometheus metrics'

# Enable firewall
sudo ufw --force enable

# Status
sudo ufw status verbose
```

## Deployment Strategy

### Production Deployment Pipeline

#### 1. Build Process
```bash
#!/bin/bash
# Production build script

set -euo pipefail

BUILD_DIR="/tmp/rockpi-build"
DEST_DIR="/opt/rockpi-provisioning"

# Create build environment
python3 -m venv "${BUILD_DIR}/venv"
source "${BUILD_DIR}/venv/bin/activate"

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .

# Run tests
python -m pytest tests/ -v --cov=src --cov-report=html

# Security scan
bandit -r src/ -f json -o security-report.json

# Build documentation
# sphinx-build -b html docs/ docs/_build/html

# Package for deployment
tar -czf rockpi-provisioning-production.tar.gz \
    src/ config/ scripts/ requirements.txt \
    pyproject.toml LICENSE README.md

echo "Production build complete: rockpi-provisioning-production.tar.gz"
```

#### 2. Deployment Script
```bash
#!/bin/bash
# Production deployment script

set -euo pipefail

PACKAGE="rockpi-provisioning-production.tar.gz"
INSTALL_DIR="/opt/rockpi-provisioning"
SERVICE_NAME="rockpi-provisioning"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Stop existing service
stop_service() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "Stopping existing service..."
        sudo systemctl stop "$SERVICE_NAME"
    fi
}

# Backup existing installation
backup_existing() {
    if [[ -d "$INSTALL_DIR" ]]; then
        local backup_dir="/opt/backups/rockpi-$(date +%Y%m%d-%H%M%S)"
        log "Backing up to $backup_dir"
        sudo mkdir -p "$(dirname "$backup_dir")"
        sudo cp -r "$INSTALL_DIR" "$backup_dir"
    fi
}

# Install new version
install_package() {
    log "Installing new version..."

    # Create installation directory
    sudo mkdir -p "$INSTALL_DIR"

    # Extract package
    sudo tar -xzf "$PACKAGE" -C "$INSTALL_DIR"

    # Create virtual environment
    cd "$INSTALL_DIR"
    sudo python3 -m venv venv
    sudo chown -R production:production "$INSTALL_DIR"

    # Install dependencies as production user
    sudo -u production "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    sudo -u production "$INSTALL_DIR/venv/bin/pip" install -r requirements.txt
    sudo -u production "$INSTALL_DIR/venv/bin/pip" install -e .
}

# Configure service
configure_service() {
    log "Configuring systemd service..."

    # Install service file
    sudo cp scripts/rockpi-provisioning.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
}

# Start service
start_service() {
    log "Starting service..."
    sudo systemctl start "$SERVICE_NAME"

    # Check status
    sleep 5
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "Service started successfully"
    else
        log "ERROR: Service failed to start"
        sudo systemctl status "$SERVICE_NAME"
        exit 1
    fi
}

# Main deployment
main() {
    log "Starting production deployment..."

    stop_service
    backup_existing
    install_package
    configure_service
    start_service

    log "Deployment completed successfully"
}

main "$@"
```

### Blue-Green Deployment
```bash
#!/bin/bash
# Blue-Green deployment for zero downtime

BLUE_DIR="/opt/rockpi-provisioning-blue"
GREEN_DIR="/opt/rockpi-provisioning-green"
CURRENT_LINK="/opt/rockpi-provisioning"

# Determine inactive environment
if [[ "$(readlink "$CURRENT_LINK")" == "$BLUE_DIR" ]]; then
    INACTIVE_DIR="$GREEN_DIR"
    ACTIVE_DIR="$BLUE_DIR"
else
    INACTIVE_DIR="$BLUE_DIR"
    ACTIVE_DIR="$GREEN_DIR"
fi

# Deploy to inactive environment
deploy_to_inactive() {
    log "Deploying to inactive environment: $INACTIVE_DIR"

    # Install to inactive directory
    sudo rm -rf "$INACTIVE_DIR"
    sudo mkdir -p "$INACTIVE_DIR"
    sudo tar -xzf "$PACKAGE" -C "$INACTIVE_DIR"

    # Setup virtual environment
    cd "$INACTIVE_DIR"
    sudo python3 -m venv venv
    sudo chown -R production:production "$INACTIVE_DIR"
    sudo -u production "$INACTIVE_DIR/venv/bin/pip" install -r requirements.txt
    sudo -u production "$INACTIVE_DIR/venv/bin/pip" install -e .
}

# Switch to new environment
switch_environment() {
    log "Switching to new environment..."

    # Update service to point to new directory
    sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INACTIVE_DIR|" \
        /etc/systemd/system/rockpi-provisioning.service
    sudo sed -i "s|ExecStart=.*|ExecStart=$INACTIVE_DIR/venv/bin/python -m src|" \
        /etc/systemd/system/rockpi-provisioning.service

    # Reload and restart
    sudo systemctl daemon-reload
    sudo systemctl restart rockpi-provisioning

    # Update symlink
    sudo rm -f "$CURRENT_LINK"
    sudo ln -sf "$INACTIVE_DIR" "$CURRENT_LINK"

    log "Environment switched successfully"
}
```

## Compliance & Legal Considerations

### Regulatory Compliance

#### FCC/CE Certification for WiFi/Bluetooth
- **ROCK Pi 4B+** has FCC ID and CE marking
- **Your software** doesn't require additional certification
- **Combined product** may need testing if in enclosure

#### Industry Standards
- **ISO 27001**: Information security management
- **GDPR**: Data protection (if collecting user data)
- **SOC 2**: Security and availability controls

### Intellectual Property Considerations

#### Patent Landscape
- **Bluetooth**: Covered by Bluetooth SIG licensing
- **WiFi**: IEEE 802.11 standards, no licensing needed
- **QR Codes**: Patent-free (Denso Wave made them open)

#### Trademark Considerations
- ✅ "ROCK Pi" is Radxa's trademark (using hardware legitimately)
- ⚠️ Avoid using "ROCK Pi" in your product naming
- ✅ Can state "Compatible with ROCK Pi 4B+"

### Data Privacy & Security

#### GDPR Compliance Checklist
- [ ] Data processing lawful basis identified
- [ ] Privacy notice provided to users
- [ ] Data retention policies implemented
- [ ] Data subject rights procedures
- [ ] Data breach notification procedures

#### Data Handling
```python
# Example GDPR-compliant data handling
class GDPRCompliantUserData:
    """GDPR-compliant user data handling"""

    def __init__(self):
        self.retention_period = timedelta(days=30)  # Configurable
        self.encryption_key = self._get_encryption_key()

    def collect_data(self, data: dict, consent: bool) -> bool:
        """Collect data only with explicit consent"""
        if not consent:
            raise ValueError("Data collection requires explicit consent")

        # Encrypt sensitive data
        encrypted_data = self._encrypt_data(data)

        # Store with timestamp for retention
        self._store_with_timestamp(encrypted_data)
        return True

    def purge_expired_data(self) -> int:
        """Automatically purge data past retention period"""
        cutoff_date = datetime.now() - self.retention_period
        return self._delete_data_before(cutoff_date)
```

## Support & Maintenance

### Long-Term Support Strategy

#### Hardware Support Timeline
- **ROCK Pi 4B+**: Supported until 2029 by Radxa
- **OP1 Processor**: Long-term availability guaranteed
- **Component lifecycle**: 7-10 years typical

#### Software Maintenance
```bash
# Automated update script for production
#!/bin/bash
# /opt/rockpi-provisioning/scripts/update-production.sh

set -euo pipefail

REPO_URL="https://github.com/your-org/rockpi-provisioning"
CURRENT_VERSION=$(cat /opt/rockpi-provisioning/VERSION)
BACKUP_DIR="/opt/backups"

# Check for updates
check_updates() {
    log "Checking for updates..."

    # Get latest version from repository
    LATEST_VERSION=$(curl -s "${REPO_URL}/releases/latest" | grep -o '"tag_name": "v[^"]*' | cut -d'"' -f4)

    if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
        log "Update available: $CURRENT_VERSION -> $LATEST_VERSION"
        return 0
    else
        log "No updates available"
        return 1
    fi
}

# Automated backup before update
backup_current() {
    local backup_path="${BACKUP_DIR}/$(date +%Y%m%d-%H%M%S)-${CURRENT_VERSION}"
    sudo mkdir -p "$backup_path"
    sudo cp -r /opt/rockpi-provisioning/* "$backup_path/"
    log "Backup created: $backup_path"
}

# Download and apply update
apply_update() {
    log "Applying update to $LATEST_VERSION"

    # Download new version
    wget "${REPO_URL}/releases/download/${LATEST_VERSION}/rockpi-provisioning-${LATEST_VERSION}.tar.gz"

    # Deploy using blue-green strategy
    ./deploy-blue-green.sh "rockpi-provisioning-${LATEST_VERSION}.tar.gz"

    log "Update completed successfully"
}

# Main update process
if check_updates; then
    backup_current
    apply_update
fi
```

### Monitoring & Alerting

#### Production Monitoring Setup
```yaml
# docker-compose.yml for monitoring stack
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password_change_me

  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml

volumes:
  prometheus_data:
  grafana_data:
```

#### Health Check Endpoint
```python
# src/monitoring/health.py
@dataclass
class SystemHealth:
    """Production health monitoring"""

    def get_health_status(self) -> Dict[str, Any]:
        """Comprehensive health check for production monitoring"""

        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": self.get_version(),
            "uptime_seconds": self.get_uptime(),
            "components": {}
        }

        # Check critical components
        components = [
            ("bluetooth", self._check_bluetooth),
            ("network", self._check_network),
            ("display", self._check_display),
            ("storage", self._check_storage),
            ("temperature", self._check_temperature),
        ]

        overall_healthy = True

        for name, check_func in components:
            try:
                component_health = check_func()
                health["components"][name] = component_health
                if component_health["status"] != "healthy":
                    overall_healthy = False
            except Exception as e:
                health["components"][name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_healthy = False

        health["status"] = "healthy" if overall_healthy else "degraded"
        return health
```

## Conclusion

### Production Readiness Checklist

#### ✅ Legal & Licensing
- [ ] MIT license allows commercial use
- [ ] No licensing fees required
- [ ] Attribution requirements understood
- [ ] Dependency licenses verified

#### ✅ Operating System
- [ ] Radxa Debian 11 selected for LTS support
- [ ] Official image downloaded and verified
- [ ] Hardware optimizations configured
- [ ] Security hardening applied

#### ✅ Deployment
- [ ] Blue-green deployment strategy implemented
- [ ] Automated backup procedures
- [ ] Health monitoring configured
- [ ] Update mechanisms in place

#### ✅ Compliance
- [ ] Data privacy policies implemented
- [ ] Security audit completed
- [ ] Regulatory requirements reviewed
- [ ] Support procedures documented

### Next Steps

1. **Immediate Actions**:
   - Download official Radxa Debian 11 image
   - Test deployment scripts in staging environment
   - Implement security hardening measures

2. **Pre-Production**:
   - Conduct security audit
   - Performance testing under load
   - Documentation review and updates

3. **Production Deployment**:
   - Gradual rollout with monitoring
   - Backup and recovery testing
   - Long-term support contract evaluation

### Support Resources

- **Radxa Wiki**: https://wiki.radxa.com/Rock4
- **Community Forum**: https://forum.radxa.com/c/rockpi4
- **Technical Support**: Available until 2029
- **Hardware Lifecycle**: 7-10 years expected

This guide provides a solid foundation for deploying the ROCK Pi 4B+ Digital Signage Provisioning System in production environments with appropriate licensing, security, and compliance considerations.

## How Python Code Actually Runs on the Board

### Direct Command Execution

The Python application can be run in several ways on the ROCK Pi 4B+ board:

#### 1. **Direct Python Execution (Development/Testing)**
```bash
# Navigate to project directory
cd /opt/rockpi-provisioning

# Activate virtual environment
source venv/bin/activate

# Run the main application directly
python3 -m src

# Or run with explicit path
python3 src/__main__.py

# Or with full Python path
/opt/rockpi-provisioning/venv/bin/python -m src
```

#### 2. **SystemD Service (Production Recommended)**
```bash
# Start the service
sudo systemctl start rockpi-provisioning

# Enable auto-start on boot
sudo systemctl enable rockpi-provisioning

# Check status
sudo systemctl status rockpi-provisioning

# View logs
sudo journalctl -u rockpi-provisioning -f

# Stop service
sudo systemctl stop rockpi-provisioning
```

#### 3. **Shell Script Wrapper (Alternative)**
```bash
#!/bin/bash
# /opt/rockpi-provisioning/start.sh

cd /opt/rockpi-provisioning
source venv/bin/activate
exec python3 -m src
```

### Production SystemD Service Configuration

#### Complete Service File: `/etc/systemd/system/rockpi-provisioning.service`
```ini
[Unit]
Description=ROCK Pi 4B+ Digital Signage Provisioning Service
Documentation=https://github.com/your-org/rockpi-provisioning
After=network.target bluetooth.target display-manager.service
Wants=network.target bluetooth.target
StartLimitIntervalSec=30
StartLimitBurst=3

[Service]
# Service execution
Type=exec
User=production
Group=production
WorkingDirectory=/opt/rockpi-provisioning

# Main command - this is how Python actually runs
ExecStart=/opt/rockpi-provisioning/venv/bin/python -m src
ExecReload=/bin/kill -HUP $MAINPID

# Restart behavior
Restart=always
RestartSec=10
TimeoutStartSec=30
TimeoutStopSec=15

# Output handling
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rockpi-provisioning

# Environment variables
Environment=PYTHONPATH=/opt/rockpi-provisioning
Environment=ROCKPI_ENV=production
Environment=ROCKPI_CONFIG_PATH=/opt/rockpi-provisioning/config/production.json
Environment=ROCKPI_LOG_LEVEL=INFO

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/rockpi-provisioning/logs
ReadWritePaths=/opt/rockpi-provisioning/config
ReadWritePaths=/opt/rockpi-provisioning/data

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096
MemoryHigh=512M
MemoryMax=1G

[Install]
WantedBy=multi-user.target
```

### Startup Shell Scripts

#### Main Startup Script: `/opt/rockpi-provisioning/scripts/start-service.sh`
```bash
#!/bin/bash
# Production startup script for ROCK Pi 4B+

set -euo pipefail

# Configuration
SERVICE_NAME="rockpi-provisioning"
PROJECT_DIR="/opt/rockpi-provisioning"
LOG_FILE="/var/log/rockpi-startup.log"
PYTHON_ENV="$PROJECT_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        error "Do not run as root. Use 'sudo systemctl start $SERVICE_NAME' instead."
        exit 1
    fi
}

# Verify Python environment
check_python_environment() {
    log "Checking Python environment..."

    if [[ ! -d "$PYTHON_ENV" ]]; then
        error "Python virtual environment not found at $PYTHON_ENV"
        exit 1
    fi

    if [[ ! -f "$PYTHON_ENV/bin/python" ]]; then
        error "Python executable not found in virtual environment"
        exit 1
    fi

    # Test Python installation
    if ! "$PYTHON_ENV/bin/python" -c "import src" 2>/dev/null; then
        error "Python application module 'src' cannot be imported"
        exit 1
    fi

    log "Python environment OK"
}

# Check hardware requirements
check_hardware() {
    log "Checking hardware compatibility..."

    # Check if ROCK Pi 4B+
    if [[ -f "/sys/firmware/devicetree/base/model" ]]; then
        local model=$(cat /sys/firmware/devicetree/base/model)
        if echo "$model" | grep -qi "rock.*4.*plus"; then
            log "Hardware: ROCK Pi 4B+ detected"
        else
            warn "Hardware: May not be ROCK Pi 4B+ - detected: $model"
        fi
    fi

    # Check Bluetooth
    if ! command -v bluetoothctl &> /dev/null; then
        error "Bluetooth tools not installed"
        exit 1
    fi

    # Check display
    if ! command -v xrandr &> /dev/null; then
        warn "Display tools not found - HDMI output may not work"
    fi

    log "Hardware check complete"
}

# Check system dependencies
check_dependencies() {
    log "Checking system dependencies..."

    local deps=("systemctl" "python3" "bluetoothctl" "iwconfig")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing dependencies: ${missing[*]}"
        exit 1
    fi

    log "Dependencies OK"
}

# Start the service
start_service() {
    log "Starting $SERVICE_NAME service..."

    # Check if already running
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        warn "Service is already running"
        return 0
    fi

    # Start service
    if sudo systemctl start "$SERVICE_NAME"; then
        log "Service started successfully"

        # Wait for startup
        sleep 3

        # Verify it's running
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log "Service is running and healthy"

            # Show status
            sudo systemctl status "$SERVICE_NAME" --no-pager
        else
            error "Service failed to start properly"
            sudo systemctl status "$SERVICE_NAME" --no-pager
            exit 1
        fi
    else
        error "Failed to start service"
        exit 1
    fi
}

# Enable auto-start
enable_autostart() {
    log "Enabling auto-start on boot..."

    if sudo systemctl enable "$SERVICE_NAME"; then
        log "Auto-start enabled"
    else
        warn "Failed to enable auto-start"
    fi
}

# Main execution
main() {
    log "=== ROCK Pi 4B+ Provisioning Service Startup ==="

    check_permissions
    check_python_environment
    check_hardware
    check_dependencies
    start_service
    enable_autostart

    log "=== Startup Complete ==="
    log "Monitor with: sudo journalctl -u $SERVICE_NAME -f"
    log "Stop with: sudo systemctl stop $SERVICE_NAME"
}

# Handle script arguments
case "${1:-start}" in
    start)
        main
        ;;
    stop)
        log "Stopping $SERVICE_NAME..."
        sudo systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        log "Restarting $SERVICE_NAME..."
        sudo systemctl restart "$SERVICE_NAME"
        ;;
    status)
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;
    logs)
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
```

#### Development Startup Script: `/opt/rockpi-provisioning/scripts/dev-start.sh`
```bash
#!/bin/bash
# Development startup script (runs in foreground with debug output)

set -euo pipefail

PROJECT_DIR="/opt/rockpi-provisioning"
PYTHON_ENV="$PROJECT_DIR/venv"

cd "$PROJECT_DIR"

# Activate virtual environment
source "$PYTHON_ENV/bin/activate"

# Set development environment
export ROCKPI_ENV=development
export ROCKPI_LOG_LEVEL=DEBUG
export PYTHONPATH="$PROJECT_DIR"

# Show startup info
echo "=== Development Mode ==="
echo "Project Dir: $PROJECT_DIR"
echo "Python: $(which python)"
echo "Environment: $ROCKPI_ENV"
echo "Log Level: $ROCKPI_LOG_LEVEL"
echo "========================"

# Run with debug output
python -m src --verbose

```

### Boot Process Flow

#### What Happens When ROCK Pi 4B+ Boots:

```bash
# 1. System Boot
BIOS/UEFI → Kernel → SystemD Init

# 2. SystemD Target: multi-user.target
systemctl list-dependencies multi-user.target

# 3. Our Service Starts
systemd[1]: Starting ROCK Pi 4B+ Digital Signage Provisioning Service...

# 4. Service Execution
/opt/rockpi-provisioning/venv/bin/python -m src

# 5. Python Application Starts
src/__main__.py → main() → ProvisioningOrchestrator.run()

# 6. Event Loops Begin
- State management loop
- Display loop
- Bluetooth service loop
- Network monitoring loop
- Health monitoring loop
```

### Manual Operation Commands

#### For Development/Testing:
```bash
# Direct Python execution
cd /opt/rockpi-provisioning
source venv/bin/activate
python -m src

# With debug output
ROCKPI_LOG_LEVEL=DEBUG python -m src --verbose

# Run specific module
python -c "from src.application.provisioning_orchestrator import main; import asyncio; asyncio.run(main())"
```

#### For Production Operations:
```bash
# Service management
sudo systemctl start rockpi-provisioning     # Start
sudo systemctl stop rockpi-provisioning      # Stop
sudo systemctl restart rockpi-provisioning   # Restart
sudo systemctl status rockpi-provisioning    # Status
sudo systemctl enable rockpi-provisioning    # Auto-start on boot
sudo systemctl disable rockpi-provisioning   # Disable auto-start

# Monitoring
sudo journalctl -u rockpi-provisioning -f    # Live logs
sudo journalctl -u rockpi-provisioning -n 50 # Last 50 lines
sudo systemctl is-active rockpi-provisioning # Check if running
sudo systemctl is-enabled rockpi-provisioning # Check if auto-start enabled
```

### Installation Command Sequence

#### Complete Installation Process:
```bash
# 1. Download and extract
cd /opt
sudo wget https://github.com/your-org/rockpi-provisioning/releases/latest/download/rockpi-provisioning-production.tar.gz
sudo tar -xzf rockpi-provisioning-production.tar.gz
sudo mv rockpi-provisioning-* rockpi-provisioning

# 2. Setup permissions
sudo chown -R production:production /opt/rockpi-provisioning
sudo chmod +x /opt/rockpi-provisioning/scripts/*.sh

# 3. Create virtual environment and install
cd /opt/rockpi-provisioning
sudo -u production python3 -m venv venv
sudo -u production venv/bin/pip install --upgrade pip
sudo -u production venv/bin/pip install -r requirements.txt
sudo -u production venv/bin/pip install -e .

# 4. Install systemd service
sudo cp scripts/rockpi-provisioning.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Start service
sudo ./scripts/start-service.sh

# 6. Verify installation
sudo systemctl status rockpi-provisioning
```

### Troubleshooting Commands

```bash
# Check if Python can import the module
/opt/rockpi-provisioning/venv/bin/python -c "import src; print('Import successful')"

# Test Bluetooth availability
bluetoothctl list

# Test display capability
xrandr --query

# Check network interfaces
ip addr show

# Monitor system resources
htop

# Check service logs for errors
sudo journalctl -u rockpi-provisioning --since "10 minutes ago"

# Run in debug mode (kills service first)
sudo systemctl stop rockpi-provisioning
cd /opt/rockpi-provisioning && ./scripts/dev-start.sh
```
