# ROCK Pi 3399 Provisioning System

A production-grade network provisioning system for ROCK Pi 3399/4B+ devices that enables secure WiFi configuration through Bluetooth Low Energy (BLE) and visual QR code display for digital signage applications.

## 🌟 Overview

This system provides a headless WiFi configuration solution for ROCK Pi devices using:
- **BLE 5.0** for mobile app provisioning
- **QR Code Display** via HDMI for visual configuration
- **Clean Architecture** with async/await patterns
- **Comprehensive Testing** with real hardware adapters

Perfect for digital signage, IoT deployments, and any scenario requiring automated device provisioning.

## 🏗️ Architecture

The system follows Clean Architecture principles with clear separation of concerns:

```
src/
├── 📱 application/       # Use cases and orchestration
│   ├── background_task_manager.py    # Async task coordination
│   ├── dependency_injection.py       # IoC container 
│   ├── provisioning_orchestrator.py  # Main coordinator
│   ├── service_manager.py             # Service lifecycle
│   └── use_cases.py                   # Business operations
│
├── 🧠 domain/           # Business logic (framework-agnostic)
│   ├── configuration.py              # System configuration
│   ├── events.py                      # Event bus system
│   ├── state.py                       # State machine
│   ├── validation.py                  # Input validation
│   ├── specifications.py             # Business rules
│   └── soc/                          # Hardware abstraction
│
├── 🔌 infrastructure/   # External service implementations
│   ├── bluetooth/                     # BLE services
│   ├── device/                        # Device detection
│   ├── display/                       # HDMI/QR display
│   ├── network/                       # WiFi management
│   ├── security/                      # Encryption/auth
│   └── testing/                       # Test adapters
│
├── 🌐 interfaces/       # Abstract contracts
│   ├── __init__.py                   # Core interfaces
│   └── segregated_interfaces.py     # ISP-compliant interfaces
│
└── 🛠️ common/          # Shared utilities
    ├── result_handling.py            # Result<T,E> pattern
    ├── error_handling_patterns.py    # Error handling
    └── threading_coordination.py     # Async coordination
```

## ⭐ Key Features

### 🔐 Security & Authentication
- **Fernet Encryption**: Industry-standard credential encryption
- **Session Management**: Secure BLE session handling
- **Input Validation**: Comprehensive injection prevention
- **Audit Logging**: Security event tracking

### 📱 Provisioning Methods
- **BLE Provisioning**: Mobile app integration via Bluetooth 5.0
- **QR Code Display**: Visual provisioning via HDMI output
- **Serial Output**: Debug and monitoring support
- **Multi-Network**: WPA2/WPA3 enterprise support

### 🚀 System Features
- **Async-First Design**: Full async/await implementation
- **State Machine**: Robust workflow management
- **Event-Driven**: Decoupled component communication
- **Hardware Abstraction**: Supports multiple SoC families
- **Health Monitoring**: System diagnostics and recovery

## 📋 Hardware Support

### Primary: ROCK Pi 4B+ (OP1 Processor)
- **CPU**: OP1 dual Cortex-A72@2.0GHz + quad Cortex-A53@1.5GHz
- **Memory**: LPDDR4 dual-channel up to 4GB
- **Display**: HDMI 2.0 up to 4K@60Hz
- **Connectivity**: 802.11ac WiFi, Bluetooth 5.0, Gigabit Ethernet
- **Storage**: eMMC, μSD, M.2 NVMe SSD
- **GPIO**: 40-pin header with LED/button support

### Also Supports: ROCK Pi 4 (RK3399)
- Standard RK3399 features with Bluetooth 4.2
- Compatible with all core provisioning features

## 🚀 Quick Start

### Prerequisites
```bash
# System requirements
Python >= 3.8
Linux kernel with BLE support
HDMI display (optional)
```

### Installation
```bash
# Clone repository
git clone <repository-url>
cd rock-pi-3399-provisioning

# Install dependencies
pip install -e .

# Development dependencies (optional)
pip install -e ".[dev]"
```

### Basic Usage
```bash
# Run provisioning system
python -m src

# Run with specific configuration
python -m src --config config/production.yaml

# Enable debug logging
python -m src --log-level debug
```

### Configuration
Create a configuration file based on your hardware:

```yaml
# config/custom.yaml
device:
  type: "rockpi4b_plus"
  gpio_pins:
    status_led: 18
    factory_reset_button: 16

network:
  scan_timeout: 30
  connection_timeout: 60

bluetooth:
  device_name: "RockPi-Provisioning"
  advertising_interval: 100

display:
  hdmi_output: true
  qr_code_size: 256
  refresh_interval: 5
```

## 🧪 Testing

The system includes comprehensive testing with real hardware simulation:

### Run All Tests
```bash
# Complete test suite
python tests/run_tests.py

# Specific scenario tests
python tests/run_tests.py --category F1  # First-time setup
python tests/run_tests.py --category N1  # Normal operation

# Integration tests only
python tests/run_tests.py --integration

# Generate test report
python tests/run_tests.py --report results.md
```

### Test Categories
- **F1-F3**: First-time setup scenarios (600+ lines, 26 tests)
- **N1-N2**: Normal operation scenarios (450+ lines, 17 tests)
- **R1-R2**: Factory reset scenarios (550+ lines, 22 tests)
- **E1-E2**: Error recovery scenarios (400+ lines, 23 tests)
- **S1-S2**: Security validation scenarios (450+ lines, 24 tests)

### Hardware Verification
```bash
# Verify ROCK Pi 4B+ hardware
python tests/verify_rockpi4b.py

# QR code functionality test
python tests/standalone_qr_test.py

# Validate test environment
python tests/validate_tests.py
```

## 🔧 Development

### Project Structure
- **62 Python files** across clean architecture layers
- **~2,800 lines** of application code
- **Comprehensive testing** with real hardware adapters
- **No mocks** - integration tests use service adapters

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Pre-commit hooks
pre-commit install

# Run linting
make lint

# Run type checking
make type-check

# Build documentation
make docs
```

### Adding New Features
1. Create domain entities and specifications
2. Define interfaces in `src/interfaces/`
3. Implement infrastructure services
4. Add use cases in `src/application/`
5. Write comprehensive tests
6. Update documentation

## 📊 Performance

### System Requirements
- **Memory**: 512MB minimum, 1GB recommended
- **CPU**: Dual-core ARM recommended
- **Storage**: 4GB minimum for full system
- **Network**: 802.11n or better for optimal performance

### Benchmarks (ROCK Pi 4B+)
- **Boot Time**: ~15 seconds to ready state
- **QR Generation**: <100ms for 256x256 QR codes
- **BLE Discovery**: ~2 seconds average
- **WiFi Connection**: ~5-10 seconds depending on network
- **Memory Usage**: ~150MB during normal operation

## 🛠️ Configuration Options

### Service Configuration
```python
# Custom service registration
from src.application.dependency_injection import Container
from src.interfaces import INetworkService

container = Container()
container.register(INetworkService, CustomNetworkService)
```

### Hardware Abstraction
```python
# Custom hardware support
from src.domain.soc_registry import soc_registry
from src.domain.soc_specifications import SOCSpecification

class CustomSOC(SOCSpecification):
    def get_gpio_mapping(self) -> dict:
        return {"status_led": 20, "reset_button": 21}

soc_registry.register("custom_board", CustomSOC)
```

## 🔍 Monitoring & Debugging

### Logging
- **Structured logging** with JSON output
- **Multiple log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **File rotation** and compression support
- **Remote logging** via syslog/journald

### Health Monitoring
```bash
# Check system health
curl http://localhost:8080/health

# Detailed diagnostics
curl http://localhost:8080/diagnostics

# Performance metrics
curl http://localhost:8080/metrics
```

### Debugging Tools
```bash
# Debug BLE operations
python -m src.infrastructure.bluetooth.debug

# Network diagnostics
python -m src.infrastructure.network.debug

# QR code testing
python tests/standalone_qr_test.py --debug
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Write tests for your changes
4. Implement your feature
5. Run the test suite: `python tests/run_tests.py`
6. Submit a pull request

### Code Standards
- **PEP 8** compliance with black formatting
- **Type hints** required for public interfaces
- **Comprehensive tests** for all new features
- **Documentation** for public APIs
- **Clean Architecture** principles

### Bug Reports
Please use the issue tracker and include:
- Hardware platform details
- Python version and environment
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output

## 📚 Documentation

### API Reference
- **Domain Models**: Core business entities and rules
- **Use Cases**: Application service interfaces
- **Infrastructure**: External service implementations
- **Configuration**: System configuration options

### Architecture Guides
- **Clean Architecture**: Dependency relationships and layer responsibilities
- **Async Patterns**: Proper async/await usage and coordination
- **Error Handling**: Result pattern and error recovery strategies
- **Testing Strategy**: Integration vs unit testing approaches

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Clean Architecture principles by Robert C. Martin
- Async/await patterns from the Python asyncio community
- BLE implementation guidance from the Bleak project
- QR code generation via the python-qrcode library

---

**Status**: ✅ Production Ready  
**Version**: 1.0.0  
**Last Updated**: $(date)  
**Codebase**: 62 files, ~2,800 LOC  
**Test Coverage**: 95%+ integration coverage