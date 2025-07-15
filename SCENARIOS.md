# Rock Pi 3399 Provisioning System - Complete Scenario Documentation

This document provides a comprehensive overview of all possible scenarios where the Rock Pi 3399 Network Provisioning System can operate, including detailed workflows, state transitions, and user interactions.

## 🎯 Overview

The Rock Pi 3399 Provisioning System enables secure WiFi configuration through multiple channels:
- **Visual Interface**: QR code displayed on HDMI output
- **Wireless Interface**: Bluetooth Low Energy (BLE) communication
- **Security Layer**: Optional owner authentication with PIN
- **Recovery System**: Factory reset via hardware button

## 📋 System Components

### Core Services
- **Network Service**: WiFi scanning, connection, and management
- **Bluetooth Service**: BLE advertising and credential reception
- **Display Service**: QR code generation and status display
- **Security Service**: Encryption and session management
- **Ownership Service**: Device owner registration and authentication
- **Factory Reset Service**: Hardware reset button monitoring

### State Machine
The system operates through a well-defined state machine with the following states:
- `INITIALIZING` - System startup and initialization
- `READY` - Ready for operations, owner registered (if required)
- `PROVISIONING` - Active provisioning mode with QR/BLE
- `CONNECTED` - Successfully connected to WiFi network
- `ERROR` - Error state requiring intervention
- `FACTORY_RESET` - Reset mode, clearing all configurations

## 🚀 Complete Scenario Breakdown

### Scenario 1: First-Time Setup (Clean Device)

**Prerequisites:**
- Fresh Rock Pi 3399 device
- HDMI display connected
- No previous WiFi configuration
- No owner registration (if required)

**Workflow:**

1. **System Startup**
   ```
   State: INITIALIZING → READY/PROVISIONING
   ```
   - Device boots and initializes all services
   - Checks for existing network configuration (none found)
   - Checks owner registration requirements

2. **Owner Setup (If Required)**
   ```
   State: INITIALIZING → READY
   Event: START_OWNER_SETUP → OWNER_REGISTERED
   ```
   - If `require_owner_setup: true` in configuration
   - Display shows owner setup instructions
   - User must register via mobile app with:
     - Device name (e.g., "Living Room Pi")
     - 6-digit PIN (meeting complexity requirements)
   - System validates PIN complexity and registers owner
   - State transitions to READY

3. **Provisioning Mode Activation**
   ```
   State: READY → PROVISIONING
   Event: START_PROVISIONING
   ```
   - System generates unique QR code containing:
     - Device ID: `ROCKPI:{device_id}:{mac_address}`
     - BLE service UUID
     - Connection parameters
   - QR code displayed full-screen on HDMI output
   - BLE advertising starts with device name "RockPi-Setup"

4. **Mobile App Interaction**
   - User scans QR code with compatible mobile app
   - App extracts device information and connects to BLE service
   - BLE service presents characteristics:
     - WiFi Credentials (write)
     - Device Status (read/notify)
     - Device Info (read)

5. **Credential Transmission**
   ```
   State: PROVISIONING
   Event: CREDENTIALS_RECEIVED
   ```
   - Mobile app sends encrypted WiFi credentials via BLE:
     - SSID (network name)
     - Password (encrypted)
   - System validates credentials format and security
   - Display updates: "Connecting to network..."

6. **Network Connection**
   ```
   State: PROVISIONING → CONNECTED
   Event: NETWORK_CONNECTED
   ```
   - System attempts WiFi connection
   - On success:
     - Saves network configuration securely
     - Display shows: "Connected successfully!"
     - BLE stops advertising
     - State transitions to CONNECTED
   - On failure:
     - Display shows: "Connection failed. Please try again."
     - Remains in PROVISIONING state for retry

### Scenario 2: Subsequent Startups (Configured Device)

**Prerequisites:**
- Device has valid saved WiFi configuration
- Owner already registered (if required)

**Workflow:**

1. **System Startup with Saved Config**
   ```
   State: INITIALIZING → CONNECTED
   Event: NETWORK_CONNECTED
   ```
   - Device boots and loads saved network configuration
   - Automatically attempts connection to saved WiFi network
   - If successful, directly transitions to CONNECTED state
   - No QR code display or BLE advertising needed

2. **Saved Config Failure**
   ```
   State: INITIALIZING → PROVISIONING
   Event: CONNECTION_FAILED → START_PROVISIONING
   ```
   - If saved WiFi network is unavailable or credentials invalid
   - System automatically enters provisioning mode
   - Follows same QR code + BLE workflow as first-time setup

### Scenario 3: Network Change/Re-provisioning

**Prerequisites:**
- Device previously configured
- User wants to connect to different WiFi network

**Workflow:**

1. **Manual Re-provisioning Trigger**
   - User triggers re-provisioning via:
     - Mobile app command
     - Hardware button press (if configured)
     - API call (for advanced users)

2. **Provisioning Mode Re-entry**
   ```
   State: CONNECTED → PROVISIONING
   Event: START_PROVISIONING
   ```
   - Current network connection maintained until new credentials received
   - QR code and BLE advertising restart
   - System accepts new credentials and attempts connection

3. **Network Switch**
   - New credentials validated and connection attempted
   - Old configuration overwritten only after successful connection
   - Seamless transition to new network

### Scenario 4: Owner Authentication Scenarios

**Prerequisites:**
- Device configured with `require_owner_setup: true`
- Owner registration completed

**4A: Owner PIN Authentication**
- Mobile app requests owner PIN for advanced operations
- Operations requiring owner auth:
  - Factory reset
  - Security settings changes
  - Device ownership transfer
- PIN validated against stored hash with rate limiting

**4B: Owner Lockout**
- After 3 failed PIN attempts (configurable)
- Account locked for 1 hour (configurable with exponential backoff)
- Security event logged and can trigger alerts

**4C: Owner Setup Timeout**
- If owner setup not completed within timeout (600 seconds default)
- Device enters error state
- Requires factory reset or manual intervention

### Scenario 5: Factory Reset Scenarios

**Prerequisites:**
- Hardware reset button connected to GPIO pin 18
- Device in any operational state

**5A: Hardware Button Reset**

1. **Reset Trigger**
   ```
   State: ANY → FACTORY_RESET
   Event: RESET_TRIGGERED
   ```
   - User holds hardware button for 5 seconds (configurable)
   - GPIO monitoring detects button press
   - System enters factory reset mode

2. **Reset Confirmation**
   - Device displays reset confirmation screen
   - Requires confirmation code entry via mobile app
   - Code validation prevents accidental resets

3. **Reset Execution**
   - All network configurations cleared
   - Owner registration cleared
   - System returns to factory default state
   - Automatic restart to INITIALIZING state

**5B: Software-Triggered Reset**
- Owner-authenticated reset via mobile app
- API-triggered reset (with proper authentication)
- Emergency reset via configuration

**5C: Recovery Mode Reset**
- System enters recovery mode on critical errors
- Alternative reset path when normal operation fails
- Bypass normal authentication for system recovery

### Scenario 6: Error Handling and Recovery

**6A: Network Connection Failures**
```
State: PROVISIONING
Event: CONNECTION_FAILED
```
- Invalid credentials provided
- Network authentication failure
- Network unavailable
- System remains in provisioning mode for retry

**6B: Bluetooth Communication Errors**
- BLE connection drops during credential transfer
- Invalid credential format received
- Encryption/decryption errors
- System logs error and restarts BLE advertising

**6C: Display Service Errors**
- HDMI display not connected
- QR code generation failure
- System continues operation without display (BLE still functional)

**6D: Critical System Errors**
```
State: ANY → ERROR
Event: ERROR_OCCURRED
```
- Hardware failures
- Configuration corruption
- Service startup failures
- Requires manual intervention or factory reset

### Scenario 7: Security Event Scenarios

**7A: Suspicious Activity Detection**
- Multiple failed authentication attempts
- Unusual connection patterns
- Rate limiting violations
- System automatically increases security posture

**7B: Security Violations**
- Invalid credential formats
- Encryption bypassing attempts
- Unauthorized access attempts
- Events logged and can trigger lockouts

**7C: Session Management**
- Session timeouts (15 minutes default)
- Maximum concurrent sessions (5 default)
- Automatic session cleanup and token rotation

### Scenario 8: Mobile Application Integration

**8A: QR Code Scanning Flow**
1. User launches compatible mobile app
2. App camera scans QR code displayed on device
3. App extracts device information and connection parameters
4. App attempts BLE connection to device

**8B: BLE Communication Flow**
1. App connects to BLE service using advertised name
2. App reads device information characteristic
3. App writes WiFi credentials to credential characteristic
4. App monitors status characteristic for connection updates
5. App displays connection success/failure to user

**8C: Owner Management Flow**
1. First-time setup: App prompts for device name and PIN
2. Subsequent use: App may request PIN for authenticated operations
3. PIN validation with error handling and lockout protection

### Scenario 9: System Monitoring and Health

**9A: Health Monitoring**
- Continuous system health checks (30-second intervals)
- Network connectivity monitoring
- Service health verification
- Performance metrics collection

**9B: Logging and Auditing**
- Comprehensive event logging to `/var/log/rock-provisioning.log`
- Security event auditing
- Performance logging
- Log rotation and retention management

**9C: Status Reporting**
- Real-time system status available via:
  - Mobile app queries
  - System health API
  - SystemD service status
  - Log file analysis

## 🔧 Configuration Scenarios

### Production Deployment
```json
{
  "security": {
    "require_owner_setup": true,
    "enhanced_security": true,
    "strict_validation": true,
    "enable_audit_logging": true
  },
  "system": {
    "auto_start": true,
    "restart_on_failure": true
  }
}
```

### Development/Testing
```json
{
  "security": {
    "require_owner_setup": false,
    "enhanced_security": false
  },
  "logging": {
    "level": "DEBUG",
    "console_output": true
  }
}
```

### Kiosk Mode
```json
{
  "display": {
    "always_show_qr": true,
    "hide_status_info": true
  },
  "security": {
    "require_owner_setup": false
  }
}
```

## 🚨 Emergency Scenarios

### Power Loss Recovery
- System designed for graceful recovery from unexpected shutdowns
- Configuration and state persistence
- Automatic service restart
- Network reconnection on boot

### Hardware Failure Recovery
- Bluetooth adapter failure: System continues with display-only mode
- Display failure: System continues with BLE-only mode
- GPIO failure: Factory reset via software methods
- Network adapter failure: System enters error state with diagnostics

### Configuration Corruption
- Automatic fallback to default configuration
- Configuration validation on startup
- Recovery mode activation for manual intervention

## 📱 Mobile App Requirements

### Minimum Functionality
- QR code scanning capability
- Bluetooth Low Energy support
- WiFi credential input interface
- Connection status display

### Enhanced Features
- Network scanning and selection
- Owner PIN management
- Device status monitoring
- Factory reset controls
- Multiple device management

### Security Requirements
- Secure credential transmission
- PIN storage and validation
- Session management
- Certificate pinning (for HTTPS APIs)

## 🔒 Security Considerations

### Threat Model Protection
- **Eavesdropping**: BLE encryption and secure channels
- **Credential Interception**: End-to-end encryption
- **Unauthorized Access**: Owner authentication and rate limiting
- **Physical Attacks**: Factory reset protection and secure storage
- **Replay Attacks**: Session tokens and timestamps
- **Brute Force**: Rate limiting and account lockouts

### Best Practices
- Regular security updates
- Strong default configurations
- Comprehensive audit logging
- Incident response procedures
- Regular security assessments

## 🔍 Troubleshooting Common Scenarios

### QR Code Not Displaying
1. Check HDMI connection
2. Verify display service status
3. Check system logs for display errors
4. Restart display service

### BLE Connection Issues
1. Verify Bluetooth adapter functionality
2. Check BLE service advertising status
3. Restart Bluetooth service
4. Verify mobile app BLE permissions

### WiFi Connection Failures
1. Verify network availability
2. Check credential validity
3. Test network authentication method
4. Review network service logs

### Factory Reset Not Working
1. Verify GPIO button connection
2. Check button hold duration
3. Test software reset methods
4. Verify reset service status

## 📊 System Metrics and Monitoring

### Key Performance Indicators
- Provisioning success rate
- Average provisioning time
- Network connection reliability
- Security incident frequency
- System uptime and availability

### Monitoring Points
- Service health status
- Resource utilization
- Network connectivity
- Security events
- Error rates and patterns

This comprehensive scenario documentation covers all possible operational states, user interactions, and system behaviors of the Rock Pi 3399 Provisioning System. Each scenario includes state transitions, prerequisites, and detailed workflows to ensure complete understanding of system capabilities.
