# Rock Pi 3399 Network Provisioning System

A modern, production-grade network provisioning system for Rock Pi 3399 devices that enables secure WiFi configuration through Bluetooth Low Energy (BLE) and visual QR code display.

## 🌟 Overview

This system provides a comprehensive solution for configuring WiFi credentials on Rock Pi 3399 devices without requiring a keyboard, mouse, or direct network access. The device displays a QR code on its HDMI output and broadcasts a BLE service that mobile applications can connect to for credential provisioning.

## 🏗️ Architecture

The system follows **Clean Architecture** principles with clear separation of concerns:

```
📁 src/
├── 🔌 interfaces/      - Pure abstractions (contracts)
├── 🧠 domain/          - Business logic and rules
├── 🏗️ infrastructure/  - External dependencies & implementations
└── 📱 application/     - Use cases and orchestration
```

### Architecture Layers

- **Interfaces**: Pure abstractions defining contracts between layers
- **Domain**: Business logic, state machine, and validation rules
- **Infrastructure**: Concrete implementations of external services (BLE, WiFi, Display)
- **Application**: Use cases, dependency injection, and orchestration

### Benefits
- **Testable**: Each layer can be independently tested
- **Maintainable**: Clear separation of concerns
- **Flexible**: Easy to swap implementations
- **Scalable**: Modular design supports growth

## ⭐ Key Features

### 🔐 Security
- **Encrypted BLE Communication**: Secure credential transmission
- **Session Management**: Time-limited sessions with automatic cleanup
- **Input Validation**: Comprehensive validation of all inputs
- **Audit Logging**: Complete security event tracking

### 📱 User Experience
- **QR Code Display**: Full-screen visual provisioning interface
- **Mobile-First**: Designed for smartphone-based configuration
- **Real-time Status Updates**: Live feedback during provisioning
- **Success Confirmation**: Visual confirmation when connected

### 🔧 Production Ready
- **Health Monitoring**: Continuous system health checks
- **Event-Driven Architecture**: Decoupled communication via EventBus
- **State Machine**: Robust provisioning flow management
- **Comprehensive Logging**: Structured logging with rotation
- **Error Recovery**: Robust error handling and recovery mechanisms

### 🌐 Network Management
- **WiFi Auto-Connect**: Automatic connection using stored credentials
- **Network Scanning**: Detects available WiFi networks
- **Connection Validation**: Verifies network connectivity
- **Configuration Persistence**: Saves successful network configurations

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd first-provision-wifi-ble-ethernet

# Install system dependencies and Python packages
make install

# Verify installation
make test
```

### Running the System

```bash
# Run the provisioning system
make run

# Or run directly
python3 -m src

# Development mode
make dev
```

## 📋 System Requirements

- **Hardware**: Rock Pi 3399 or compatible SBC
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.8 or higher
- **Bluetooth**: BLE-capable adapter
- **Display**: HDMI output for QR code display

### Required System Packages
- `bluetooth`, `bluez`, `bluez-tools`
- `python3`, `python3-pip`, `python3-venv`
- `wpasupplicant`, `wireless-tools`
- `libglib2.0-dev`, `pkg-config`

## 🔧 Configuration

The system loads configuration from multiple sources (in order):
1. `/etc/rockpi-provisioning/config.json` (production)
2. `config/unified_config.json` (development)
3. Built-in defaults (fallback)

### Key Configuration Sections

```json
{
  "ble": {
    "device_name": "RockPi3399",
    "service_uuid": "12345678-1234-1234-1234-123456789abc",
    "advertising_interval": 100
  },
  "security": {
    "require_owner_setup": true,
    "owner_setup_timeout": 300,
    "encryption_enabled": true
  },
  "display": {
    "width": 1920,
    "height": 1080,
    "qr_size": 400
  },
  "logging": {
    "level": "INFO",
    "file_path": "logs/rockpi-provisioning.log"
  }
}
```

## 📖 Usage

### 1. Initial Setup
1. Connect Rock Pi to HDMI display
2. Power on the device
3. System will display QR code on screen

### 2. Mobile App Configuration
1. Scan QR code with compatible mobile app
2. Connect to BLE service
3. Send WiFi credentials through BLE
4. System validates and connects to network

### 3. Owner Setup (Optional)
- Register device owner with PIN
- Authenticate for advanced operations
- Manage device settings

### 4. Factory Reset
- Use hardware button or software command
- Clears all configurations and returns to initial state

## 🔌 Service Management

### Make Commands

```bash
# Installation and setup
make install        # Install system dependencies
make uninstall      # Remove installed files and services

# Development and testing
make test          # Run tests and verify installation
make run           # Run the provisioning system
make dev           # Run in development mode
make clean         # Clean build artifacts and logs

# Code quality
make lint          # Run code linting
make format        # Format code
make check         # Run all checks (lint + test)

# System management
make status        # Show system status
make logs          # Show system logs
make deps         # Install dependencies from pyproject.toml
```

### SystemD Service

```bash
# Check service status
sudo systemctl status rock-provisioning

# Start/stop service
sudo systemctl start rock-provisioning
sudo systemctl stop rock-provisioning

# Enable/disable auto-start
sudo systemctl enable rock-provisioning
sudo systemctl disable rock-provisioning

# View service logs
journalctl -u rock-provisioning -f
```

## 🏗️ Project Structure

```
📁 first-provision-wifi-ble-ethernet/
├── 📄 README.md                    # This file
├── 📄 Makefile                     # Build and development tasks
├── 📄 install.sh                   # System installation script
├── 📄 pyproject.toml             # Modern Python project config & dependencies
├── 📄 setup.py                     # Package setup
├── 📁 config/                      # Configuration files
│   └── unified_config.json
├── 📁 scripts/                     # Utility scripts
│   └── verify_installation.py
├── 📁 logs/                        # Log files (created at runtime)
└── 📁 src/                         # Source code
    ├── __init__.py
    ├── __main__.py                 # Entry point
    ├── 📁 interfaces/              # Pure abstractions
    │   ├── core_interfaces.py
    │   └── manager_interfaces.py
    ├── 📁 domain/                  # Business logic
    │   ├── configuration.py
    │   ├── state_machine.py
    │   ├── validation.py
    │   └── event_bus.py
    ├── 📁 infrastructure/          # External implementations
    │   ├── bluetooth.py
    │   ├── network.py
    │   ├── display.py
    │   ├── logging.py
    │   ├── security.py
    │   └── ownership.py
    └── 📁 application/             # Use cases & orchestration
        ├── dependency_injection.py
        ├── use_cases.py
        └── orchestrator.py
```

## 🐛 Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure dependencies are installed
make install
make test
```

**Bluetooth Issues**
```bash
# Check Bluetooth status
sudo systemctl status bluetooth
hciconfig

# Reset Bluetooth
sudo systemctl restart bluetooth
```

**Permission Issues**
```bash
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Logout and login again
```

**Configuration Issues**
```bash
# Verify configuration
python3 -c "from src.domain.configuration import load_config; print(load_config())"

# Check file permissions
ls -la config/
```

### Diagnostic Commands

```bash
# Check system status
make status

# View recent logs
make logs

# Run verification tests
make test

# Check configuration
python3 scripts/verify_installation.py
```

### Logging

Logs are written to:
- Console output (INFO level and above)
- File: `logs/rockpi-provisioning.log` (configurable)
- SystemD journal: `journalctl -u rock-provisioning`

## 🔒 Security

### Built-in Security Features
- **Encrypted Communication**: All BLE data is encrypted
- **Session Management**: Time-limited authentication sessions
- **Input Validation**: Comprehensive input sanitization
- **Audit Logging**: Security events are logged
- **Rate Limiting**: Protection against brute force attacks

### Security Best Practices
- Change default configuration values in production
- Enable audit logging for production deployments
- Regularly update dependencies
- Monitor system logs for security events

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the architecture patterns
4. Add tests for new functionality
5. Submit a pull request

### Architecture Guidelines

- **Interfaces**: Define contracts, no implementations
- **Domain**: Business logic, no external dependencies
- **Infrastructure**: External integrations, implement interfaces
- **Application**: Orchestrate use cases, wire dependencies

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Projects

- [Rock Pi Official Documentation](https://wiki.radxa.com/Rockpi4)
- [Bluetooth Low Energy Specification](https://www.bluetooth.com/specifications/bluetooth-core-specification/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

**Made with ❤️ for the Rock Pi community**

## 🚀 Development & CI/CD

### **GitHub Actions Optimized for Free Tier**

This project includes a sophisticated CI/CD pipeline optimized for GitHub Actions free tier usage:

#### **🔄 Workflow Overview**

| Workflow | Trigger | Duration | Purpose |
|----------|---------|-----------|---------|
| **🔍 PR Validation** | Pull Request | ~3-5 min | Fast feedback, code quality |
| **🚀 Optimized CI** | Push to main/develop | ~8-15 min | Standard tests + hardware validation |
| **🌙 Monthly Tests** | 1st of month | ~60-90 min | Comprehensive regression testing |

#### **💰 Cost Optimization Features**

- **Smart Change Detection**: Skips workflows for docs-only changes
- **Conditional Execution**: Hardware tests only on main branch or manual trigger
- **Efficient Caching**: Python dependencies cached across runs
- **Concurrency Control**: Cancels previous runs to save minutes
- **Self-hosted Runner**: Rock Pi 3399 handles heavy hardware testing

#### **🎣 Pre-commit Hooks**

Catch issues early to prevent failed CI runs:

```bash
# One-time setup
./setup-dev.sh

# Manual checks
pre-commit run --all-files

# Auto-runs on every commit
git commit -m "Your changes"
```

**Pre-commit checks include:**
- Code formatting (Black)
- Import sorting (isort)
- Linting (Flake8)
- Security scanning (Bandit)
- Type checking (MyPy)

#### **🔧 Self-hosted Runner Setup**

For Rock Pi 3399 hardware testing:

1. **Follow the setup guide**: `.github/SETUP_CI_CD.md`
2. **Configure your Rock Pi as a GitHub runner**
3. **Hardware tests run automatically on main branch**

#### **📊 Estimated GitHub Actions Usage**

**For Private Repositories (2,000 min/month free):**

| Scenario | Monthly Usage | Status |
|----------|---------------|---------|
| **10 PRs + 20 pushes** | ~400 minutes | ✅ Well within limits |
| **Active development** | ~800 minutes | ✅ Comfortable usage |
| **Heavy usage** | ~1,200 minutes | ⚠️ Monitor usage |

**💡 Tips to minimize usage:**
- Use draft PRs while developing
- Only push to main when ready
- Leverage self-hosted runner for hardware tests
- Use manual workflow dispatch for full testing
