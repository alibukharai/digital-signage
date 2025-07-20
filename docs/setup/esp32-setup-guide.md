# 📱 ESP32 Setup Guide for GitHub Actions Runner

## 📋 Overview

This guide provides step-by-step instructions to set up an ESP32 device as a GitHub Actions self-hosted runner for automated testing with the RockPi4B+ digital signage provisioning system.

## 🛠️ Hardware Requirements

### ESP32 Development Board Specifications

| Specification | Requirement | Recommended Model |
|---------------|-------------|-------------------|
| **MCU** | ESP32-WROOM-32 or ESP32-S3 | ESP32-DevKitC-V4 |
| **Flash Memory** | 4MB minimum, 8MB+ recommended | 8MB or 16MB |
| **SRAM** | 520KB (built-in) | Standard |
| **WiFi** | 802.11 b/g/n 2.4GHz | Built-in |
| **Bluetooth** | BLE 4.2+ / 5.0 preferred | Built-in |
| **GPIO** | 30+ pins available | Standard 38-pin |
| **USB** | USB-to-UART bridge | CP2102 or CH340 |
| **Power** | 3.3V, 500mA+ | USB or external |

## 💻 Development Environment Setup

### 1. Install PlatformIO

```bash
# Install Python if not already installed
sudo apt update
sudo apt install -y python3 python3-pip

# Install PlatformIO Core
pip3 install platformio

# Verify installation
pio --version
```

### 2. Create ESP32 Test Client Project

```bash
# Create project directory
mkdir -p /opt/esp32-test-client
cd /opt/esp32-test-client

# Initialize PlatformIO project
pio project init --board esp32dev --project-option "framework=arduino"
```

### 3. Configure PlatformIO Project

Edit `platformio.ini`:

```ini
; ESP32 Test Client Configuration
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino

; Upload settings
monitor_speed = 115200
upload_speed = 921600

; Libraries
lib_deps = 
    knolleary/PubSubClient@^2.8
    arduino-libraries/ArduinoHttpClient@^0.4.0
    bblanchon/ArduinoJson@^6.21.3
    h2zero/NimBLE-Arduino@^1.4.1
    me-no-dev/AsyncTCP@^1.1.1
    me-no-dev/ESPAsyncWebServer@^1.2.3
```

## 🔧 GitHub Actions Runner Setup

Since ESP32 can't run GitHub Actions runner directly, set up the runner on the host machine:

```bash
# Create runner directory
sudo mkdir -p /opt/esp32-actions-runner
cd /opt/esp32-actions-runner

# Download GitHub Actions runner
sudo curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

# Extract and configure
sudo tar xzf actions-runner-linux-x64-2.311.0.tar.gz

# Create runner user
sudo useradd -r -s /bin/bash esp32-runner
sudo usermod -aG dialout esp32-runner
sudo chown -R esp32-runner:esp32-runner /opt/esp32-actions-runner

# Configure runner
sudo -u esp32-runner ./config.sh --url https://github.com/your-org/digital-signage \
  --token YOUR_RUNNER_REGISTRATION_TOKEN \
  --labels esp32 \
  --name esp32-test-runner

# Install as service
sudo ./svc.sh install esp32-runner
sudo ./svc.sh start
```

## 🔍 Testing and Validation

### Local Testing

```bash
# Test serial communication
pio device monitor --port /dev/ttyUSB0 --baud 115200

# Test API endpoints
curl http://ESP32_IP:8080/health

# Test MQTT communication
mosquitto_pub -h ESP32_IP -t "test/ping" -m "hello"
```

## 🔧 Troubleshooting

### Common Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| ESP32 not detected | Device not found at /dev/ttyUSB0 | Check USB connection, install drivers |
| Build failures | PlatformIO build errors | Update libraries, check dependencies |
| WiFi connection fails | ESP32 can't connect to network | Check credentials, network settings |

## ✅ Verification Checklist

- [ ] ESP32 development board properly connected
- [ ] PlatformIO installed and configured
- [ ] Test client firmware builds successfully
- [ ] ESP32 connects to WiFi network
- [ ] MQTT communication working
- [ ] HTTP API endpoints responding
- [ ] GitHub Actions runner registered
- [ ] Integration with RockPi4B+ tested

---

For the complete architecture overview, see: `ESP32_ROCKPI_DUAL_RUNNER_ARCHITECTURE.md`