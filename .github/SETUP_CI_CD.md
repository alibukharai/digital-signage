# 🚀 GitHub Actions CI/CD Setup Guide for Rock Pi 3399

This guide walks you through setting up a comprehensive CI/CD pipeline using GitHub Actions with your Rock Pi 3399 as a self-hosted runner for hardware-specific tests.

## 📋 Overview

Our CI/CD pipeline includes:

- **🔍 Code Quality Checks** (GitHub runners) - Fast feedback on PRs
- **🧪 Unit Tests** (GitHub runners) - Cross-platform compatibility 
- **🔧 Hardware Integration Tests** (Rock Pi 3399) - Real hardware validation
- **🌐 End-to-End Tests** (Rock Pi 3399) - Complete system validation
- **🌙 Nightly Tests** (Rock Pi 3399) - Comprehensive regression testing

## 🎯 Architecture Benefits

### **Why Self-Hosted Runner on Rock Pi 3399?**

1. **🔧 Real Hardware Testing**: Tests run on actual target hardware
2. **📡 GPIO/Bluetooth/WiFi**: Access to real hardware interfaces
3. **⚡ Accurate Performance**: Real-world performance metrics
4. **🛡️ Security Validation**: Actual encryption/security testing
5. **💰 Cost Effective**: Use your existing Rock Pi 3399

### **Hybrid Approach:**
- **GitHub Runners**: Fast code quality, security scans, cross-platform tests
- **Self-Hosted Runner**: Hardware-specific, integration, and E2E tests

---

## 🔧 Part 1: Prepare Your Rock Pi 3399

### **1.1 System Requirements**

**Minimum Hardware:**
- Rock Pi 3399 (or compatible ARM64 board)
- 4GB+ RAM recommended 
- 32GB+ storage
- WiFi/Bluetooth capability
- Stable internet connection
- Optional: HDMI display for display tests

**Software Requirements:**
- Ubuntu 20.04+ or Debian 11+ (ARM64)
- Python 3.8+
- Git
- Docker (optional but recommended)

### **1.2 Install Dependencies**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  curl \
  wget \
  build-essential \
  bluetooth \
  bluez \
  bluez-tools \
  network-manager \
  gpio-utils \
  i2c-tools

# Install Node.js (required for GitHub Actions runner)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Docker (optional but recommended)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

### **1.3 Configure Hardware Interfaces**

```bash
# Enable GPIO, I2C, SPI interfaces
sudo systemctl enable gpio
sudo usermod -aG gpio $USER

# Configure Bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Verify hardware interfaces
echo "=== Hardware Interface Check ==="
echo "GPIO: $([ -d /sys/class/gpio ] && echo "✅ Available" || echo "❌ Not available")"
echo "Bluetooth: $(systemctl is-active bluetooth)"
echo "WiFi: $(iwconfig 2>/dev/null | grep -q "IEEE 802.11" && echo "✅ Available" || echo "❌ Not available")"
```

### **1.4 Create Runner User**

```bash
# Create dedicated user for GitHub Actions runner
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG sudo,gpio,bluetooth,dialout github-runner

# Set up sudo without password for automation
echo "github-runner ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/github-runner

# Switch to runner user
sudo su - github-runner
```

---

## 🎯 Part 2: Set Up Self-Hosted GitHub Actions Runner

### **2.1 Download and Configure Runner**

```bash
# Navigate to your repository on GitHub:
# Settings → Actions → Runners → New self-hosted runner

# Follow GitHub's instructions to download the runner
mkdir actions-runner && cd actions-runner

# Download the latest runner for ARM64
curl -o actions-runner-linux-arm64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz

# Verify download (check GitHub for current hash)
echo "033c23b7cd0b696b7e040c4b8a23c5e23b4ceb4eaa8866d7c0e2e89dc5ad6edb  actions-runner-linux-arm64-2.311.0.tar.gz" | shasum -a 256 -c

# Extract
tar xzf ./actions-runner-linux-arm64-2.311.0.tar.gz
```

### **2.2 Configure Runner**

```bash
# Configure the runner (replace with your repository URL and token)
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_REGISTRATION_TOKEN

# When prompted:
# - Enter name: rock-pi-3399
# - Enter labels: rock-pi-3399,arm64,hardware
# - Enter work folder: _work (default)
```

### **2.3 Install as System Service**

```bash
# Install runner as systemd service
sudo ./svc.sh install

# Start the service
sudo ./svc.sh start

# Check status
sudo ./svc.sh status

# Enable auto-start on boot
sudo systemctl enable actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service
```

### **2.4 Verify Runner Configuration**

```bash
# Check if runner is online in GitHub
# Go to: Repository → Settings → Actions → Runners
# You should see "rock-pi-3399" with status "Idle"

# Test runner with a simple job
echo "Runner configured successfully! Check GitHub repository settings."
```

---

## 🛠️ Part 3: Configure Project for CI/CD

### **3.1 Repository Secrets**

Add these secrets in your GitHub repository:
`Settings → Secrets and variables → Actions`

```bash
# Optional: Add secrets for notifications or deployments
# SLACK_WEBHOOK_URL (for notifications)
# DEPLOYMENT_KEY (for production deployments)
```

### **3.2 Configure Branch Protection**

`Repository → Settings → Branches → Add rule`

**For `main` branch:**
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Include administrators

**Required status checks:**
- `PR Quick Validation`
- `Critical Tests (PR)`

### **3.3 Environment Protection**

`Repository → Settings → Environments → New environment`

**Create `production` environment:**
- ✅ Required reviewers: (add yourself)
- ✅ Wait timer: 5 minutes
- ✅ Deployment branches: `main` only

---

## 🧪 Part 4: Test Your CI/CD Pipeline

### **4.1 Test Pull Request Workflow**

```bash
# Create a test branch
git checkout -b test-ci-pipeline

# Make a small change
echo "# CI/CD Pipeline Test" >> TEST_CI.md
git add TEST_CI.md
git commit -m "test: verify CI/CD pipeline functionality"

# Push and create PR
git push origin test-ci-pipeline
```

**Expected behavior:**
1. **PR validation** runs on GitHub runners (fast)
2. **Critical tests** run on GitHub runners
3. **No hardware tests** run until merged to main

### **4.2 Test Main Branch Workflow**

```bash
# Merge the PR through GitHub interface
# This triggers the full workflow:

# 1. Code quality checks (GitHub runners)
# 2. Unit tests (GitHub runners) 
# 3. Hardware tests (Rock Pi 3399) ✨
# 4. E2E tests (Rock Pi 3399) ✨
# 5. Release preparation
```

### **4.3 Test Manual Trigger**

```bash
# Go to: Repository → Actions → Rock Pi 3399 Provisioning System CI/CD
# Click "Run workflow"
# Choose test type: "critical"
# ✅ Generate report: true
# Click "Run workflow"
```

### **4.4 Test Nightly Workflow**

```bash
# Nightly tests run automatically at 2 AM UTC
# To test manually:
# Go to: Repository → Actions → Nightly Hardware Tests
# Click "Run workflow"
# Choose scope: "critical-only" (for testing)
```

---

## 📊 Part 5: Monitor and Maintain

### **5.1 Monitor Runner Health**

```bash
# Check runner service status
sudo systemctl status actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service

# View runner logs
sudo journalctl -u actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service -f

# Check system resources
htop
df -h
free -h
```

### **5.2 Maintenance Tasks**

**Weekly:**
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean up old test artifacts
rm -rf /tmp/rockpi_test_*
docker system prune -f  # if using Docker
```

**Monthly:**
```bash
# Update GitHub Actions runner
cd ~/actions-runner
sudo ./svc.sh stop
./config.sh remove  # remove old registration
# Download new version and reconfigure
sudo ./svc.sh install
sudo ./svc.sh start
```

### **5.3 Troubleshooting**

**Runner Not Appearing Online:**
```bash
# Check network connectivity
ping github.com

# Check runner service
sudo systemctl restart actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service

# Check logs for errors
sudo journalctl -u actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service --since "1 hour ago"
```

**Hardware Tests Failing:**
```bash
# Check hardware interfaces
sudo systemctl status bluetooth
iwconfig
ls /sys/class/gpio/

# Check permissions
groups github-runner  # should include gpio, bluetooth
```

**Performance Issues:**
```bash
# Monitor during test runs
htop
iotop  # install with: sudo apt install iotop
nethogs  # install with: sudo apt install nethogs
```

---

## 🚀 Part 6: Advanced Configuration

### **6.1 Multiple Runners**

For redundancy, set up multiple Rock Pi devices:

```bash
# On second Rock Pi:
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN
# Name: rock-pi-3399-backup
# Labels: rock-pi-3399,arm64,hardware,backup
```

### **6.2 Docker Support**

```bash
# Enable Docker for containerized tests
sudo usermod -aG docker github-runner

# Test Docker access
docker run hello-world
```

### **6.3 Custom Test Environment**

Create a custom test configuration:

```bash
# Create test environment file
cat > ~/.github-runner-env << 'EOF'
export ROCKPI_TEST_CONFIG_PATH="/home/github-runner/test-config.json"
export ROCKPI_TEST_LOG_LEVEL="INFO"
export HARDWARE_TEST_MODE="ci"
EOF

# Source in runner service
sudo systemctl edit actions.runner.YOUR_USERNAME-YOUR_REPO.rock-pi-3399.service
```

### **6.4 Notifications**

Set up Slack/Discord notifications:

```yaml
# Add to workflow files
- name: 📧 Notify on Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: failure
    webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## ✅ Summary

You now have a comprehensive CI/CD pipeline that:

### **🔄 Automated Testing:**
- **Every PR**: Fast validation and critical tests
- **Main branch**: Full hardware integration testing
- **Nightly**: Comprehensive regression testing
- **Manual**: On-demand testing with custom scopes

### **🔧 Hardware Integration:**
- Real GPIO, Bluetooth, WiFi testing
- Actual Rock Pi 3399 performance metrics
- End-to-end system validation
- Security testing on real hardware

### **📊 Quality Assurance:**
- Code formatting and linting
- Security scanning
- Test coverage reporting
- Performance benchmarking

### **🚀 Deployment Ready:**
- Manual approval gates
- Release automation
- Artifact management
- Notification systems

Your Rock Pi 3399 is now a powerful CI/CD testing node that provides real hardware validation while maintaining development velocity with hybrid cloud/self-hosted testing! 🎉

---

## 🆘 Need Help?

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Self-hosted Runners**: https://docs.github.com/en/actions/hosting-your-own-runners
- **Rock Pi 3399 Docs**: Check your board documentation
- **Issue Tracker**: Create an issue in this repository
