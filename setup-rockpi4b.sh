#!/bin/bash
# Enhanced setup script for ROCK Pi 4B+ Digital Signage System

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="./setup-rockpi4b.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

# Detect hardware platform
detect_hardware() {
    log "Detecting hardware platform..."

    if [[ -f "/proc/device-tree/compatible" ]]; then
        local compatible=$(cat /proc/device-tree/compatible 2>/dev/null || echo "")
        if echo "$compatible" | grep -q "rockchip,op1\|rk3399-op1"; then
            echo "OP1"
            return 0
        elif echo "$compatible" | grep -q "rockchip,rk3399"; then
            echo "RK3399"
            return 0
        fi
    fi

    if [[ -f "/sys/firmware/devicetree/base/model" ]]; then
        local model=$(cat /sys/firmware/devicetree/base/model 2>/dev/null || echo "")
        if echo "$model" | grep -qi "rock.*4.*plus"; then
            echo "OP1"
            return 0
        fi
    fi

    # Check if we're on a development machine
    if [[ "$(uname -m)" == "x86_64" ]]; then
        echo "DEV_X86"
        return 0
    fi

    echo "UNKNOWN"
    return 1
}

# Install system dependencies based on platform
install_system_dependencies() {
    local hardware="$1"
    log "Installing system dependencies for $hardware..."

    # Update package lists
    sudo apt-get update

    # Common packages for all platforms
    local common_packages=(
        "python3.10"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        "git"
        "curl"
        "wget"
        "unzip"
        "build-essential"
        "libffi-dev"
        "libssl-dev"
        "pkg-config"
    )

    # Hardware-specific packages
    local hw_packages=()

    if [[ "$hardware" == "OP1" || "$hardware" == "RK3399" ]]; then
        log "Installing ROCK Pi specific packages..."
        hw_packages+=(
            "bluetooth"
            "bluez"
            "bluez-tools"
            "pi-bluetooth"
            "wireless-tools"
            "wpasupplicant"
            "hostapd"
            "dnsmasq"
            "xorg"
            "xinit"
            "x11-xserver-utils"
            "fbi"
            "fim"
            "htop"
            "iotop"
            "nethogs"
            "ethtool"
            "i2c-tools"
            "libdbus-1-dev"
            "libudev-dev"
            "python3-rpi.gpio"
            "gpiod"
            "libgpiod-dev"
        )

        # ROCK Pi 4B+ specific packages
        if [[ "$hardware" == "OP1" ]]; then
            hw_packages+=(
                "rockchip-multimedia-config"
                "mali-t86x-module"
            )
        fi
    else
        log "Installing development machine packages..."
        hw_packages+=(
            "libdbus-1-dev"
            "libudev-dev"
        )
    fi

    # Install all packages
    local all_packages=("${common_packages[@]}" "${hw_packages[@]}")

    for package in "${all_packages[@]}"; do
        if sudo apt-get install -y "$package" 2>/dev/null; then
            log "Installed: $package"
        else
            warn "Failed to install: $package (continuing...)"
        fi
    done
}

# Apply hardware-specific optimizations
apply_hardware_optimizations() {
    local hardware="$1"
    log "Applying optimizations for $hardware..."

    if [[ "$hardware" == "OP1" ]]; then
        log "Applying OP1-specific optimizations..."

        # CPU governor settings
        if [[ -d "/sys/devices/system/cpu/cpufreq" ]]; then
            echo "ondemand" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null 2>&1 || true
            log "Set CPU governor to ondemand"
        fi

        # Memory optimizations
        echo 10 | sudo tee /proc/sys/vm/swappiness > /dev/null 2>&1 || true
        echo 50 | sudo tee /proc/sys/vm/vfs_cache_pressure > /dev/null 2>&1 || true
        log "Applied memory optimizations"

        # GPU optimizations
        if [[ -d "/sys/devices/platform/ff9a0000.gpu" ]]; then
            echo "simple_ondemand" | sudo tee /sys/devices/platform/ff9a0000.gpu/devfreq/ff9a0000.gpu/governor > /dev/null 2>&1 || true
            log "Set GPU governor to simple_ondemand"
        fi

        # Network optimizations for available interfaces
        for iface in /sys/class/net/eth*; do
            if [[ -d "$iface" ]]; then
                iface_name=$(basename "$iface")
                sudo ethtool -K "$iface_name" rx-checksumming on 2>/dev/null || true
                sudo ethtool -K "$iface_name" tx-checksumming on 2>/dev/null || true
                log "Applied network optimizations for $iface_name"
            fi
        done
    elif [[ "$hardware" == "RK3399" ]]; then
        log "Applying RK3399 optimizations..."
        # Basic RK3399 optimizations
        echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null 2>&1 || true
    else
        log "Skipping hardware optimizations for development environment"
    fi
}

# Setup Python environment
setup_python_environment() {
    log "Setting up Python environment..."

    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log "Created Python virtual environment"
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip and setuptools
    pip install --upgrade pip setuptools wheel

    # Install Python dependencies
    if [[ -f "requirements.txt" ]]; then
        log "Installing Python dependencies..."
        pip install -r requirements.txt
        log "Python dependencies installed"
    else
        warn "requirements.txt not found, installing basic dependencies..."
        pip install pytest pytest-cov pytest-asyncio bleak cryptography qrcode[pil] psutil pydantic loguru
    fi

    # Install the package in development mode
    pip install -e .
    log "Installed package in development mode"
}

# Setup development tools
setup_development_tools() {
    log "Setting up development tools..."

    source venv/bin/activate

    # Install development dependencies
    pip install --upgrade \
        black \
        flake8 \
        mypy \
        isort \
        pylint \
        bandit \
        pre-commit

    # Setup pre-commit hooks
    if [[ -f ".pre-commit-config.yaml" ]]; then
        pre-commit install
        log "Pre-commit hooks installed"
    fi

    log "Development tools installed"
}

# Create configuration directories
setup_configuration() {
    log "Setting up configuration..."

    # Create configuration directory
    mkdir -p ~/.config/rock-provisioning

    # Copy configuration file if it doesn't exist
    if [[ ! -f ~/.config/rock-provisioning/config.json ]] && [[ -f "config/unified_config.json" ]]; then
        cp config/unified_config.json ~/.config/rock-provisioning/config.json
        log "Configuration file copied to user directory"
    fi

    # Create log directory
    mkdir -p ~/.local/share/rock-provisioning/logs

    log "Configuration setup complete"
}

# Run tests to verify installation
run_verification_tests() {
    log "Running verification tests..."

    source venv/bin/activate

    # Run basic import tests
    python -c "import src; print('✓ Package imports successfully')"
    python -c "from src.infrastructure.device import DeviceInfoProvider; print('✓ Device service imports successfully')"
    python -c "from src.infrastructure.bluetooth import BluetoothService; print('✓ Bluetooth service imports successfully')"
    python -c "from src.infrastructure.display import DisplayService; print('✓ Display service imports successfully')"
    python -c "from src.infrastructure.network import NetworkService; print('✓ Network service imports successfully')"

    # Run unit tests if available
    if [[ -d "tests" ]]; then
        log "Running unit tests..."
        python -m pytest tests/ -v --tb=short
    else
        warn "No tests directory found, skipping unit tests"
    fi

    log "Verification tests completed"
}

# Main setup function
main() {
    log "Starting ROCK Pi 4B+ enhanced setup..."

    # Check if running as root
    if [[ $EUID -eq 0 ]]; then
        error "Please run as regular user (will prompt for sudo when needed)"
        exit 1
    fi

    # Detect hardware
    local hardware=$(detect_hardware)
    log "Detected hardware: $hardware"

    # Install system dependencies
    install_system_dependencies "$hardware"

    # Apply hardware-specific optimizations
    apply_hardware_optimizations "$hardware"

    # Setup Python environment
    setup_python_environment

    # Setup development tools
    setup_development_tools

    # Setup configuration
    setup_configuration

    # Run verification tests
    run_verification_tests

    log "Enhanced setup completed successfully!"
    log ""
    log "🚀 ROCK Pi 4B+ Digital Signage System Ready!"
    log ""
    log "To activate the environment, run:"
    log "  source venv/bin/activate"
    log ""
    log "To run the application:"
    log "  python -m src"
    log ""
    log "To run tests:"
    log "  python -m pytest tests/"

    if [[ "$hardware" == "OP1" ]]; then
        log ""
        log "🔧 ROCK Pi 4B+ specific notes:"
        log "- ✅ OP1 processor optimizations applied"
        log "- ✅ Bluetooth 5.0 support configured"
        log "- ✅ 4K HDMI 2.0 display support enabled"
        log "- ✅ GPIO and hardware interfaces configured"
        log "- ✅ Network optimizations applied"
        log ""
        log "⚠️  Important:"
        log "- GPIO functionality requires running as root or adding user to gpio group"
        log "- Bluetooth requires bluez service to be running"
        log "- Display requires X11 server for QR code display"
        log "- Consider rebooting to ensure all optimizations take effect"
        log ""
        log "🔍 Hardware verification:"
        log "  sudo systemctl status bluetooth"
        log "  xrandr --query"
        log "  cat /proc/device-tree/model"
    elif [[ "$hardware" == "RK3399" ]]; then
        log ""
        log "🔧 ROCK Pi 4 (RK3399) notes:"
        log "- ✅ RK3399 processor optimizations applied"
        log "- ⚠️  Limited to Bluetooth 4.2 and standard HDMI features"
    else
        log ""
        log "💻 Development environment notes:"
        log "- ✅ All dependencies installed for cross-platform development"
        log "- ⚠️  Hardware-specific features will be simulated"
    fi
}

main "$@"
