# 🚀 CI/CD Quick Reference Guide

## 📋 Workflow Overview

| Trigger | Workflow | Runs On | Purpose |
|---------|----------|---------|---------|
| **PR Open/Update** | PR Validation | GitHub Runners | Fast feedback, code quality |
| **Push to Main** | Full CI/CD | Hybrid (GitHub + Rock Pi) | Complete validation |
| **Schedule (2 AM)** | Nightly Tests | Rock Pi 3399 | Regression testing |
| **Manual** | Custom Tests | Rock Pi 3399 | On-demand testing |

---

## 🎯 Common Operations

### **🔍 Run Tests Manually**

```bash
# In repository: Actions → Choose workflow → Run workflow

# Options available:
- 🧪 All tests
- 🎯 Critical only  
- 🔗 Integration only
- ⚡ Performance only
- 🔒 Security only
```

### **📊 Check Test Results**

```bash
# Navigate to: Actions → Latest workflow run
# Download artifacts for detailed reports
# Check job summaries for quick overview
```

### **🔧 Debug Failed Tests**

```bash
# Local debugging on Rock Pi:
ssh github-runner@your-rock-pi-ip

# Check runner status
sudo systemctl status actions.runner.*

# View runner logs
sudo journalctl -u actions.runner.* -f

# Run tests manually
cd /path/to/repository
python run_tests.py --critical --verbose
```

---

## 🧪 Test Categories & When They Run

### **PR Validation (Every PR)**
- ✅ Code formatting (Black, isort)
- ✅ Linting (Flake8)
- ✅ Fast unit tests
- ✅ Test structure validation
- ⏱️ Duration: ~3-5 minutes

### **Hardware Tests (Main branch only)**
- ✅ GPIO functionality  
- ✅ Bluetooth/BLE operations
- ✅ WiFi connectivity
- ✅ Display interface
- ✅ Factory reset procedures
- ⏱️ Duration: ~15-30 minutes

### **Nightly Tests (Scheduled)**
- ✅ All hardware tests
- ✅ Long-running stability tests
- ✅ Performance benchmarks
- ✅ System health monitoring
- ⏱️ Duration: ~45-60 minutes

---

## 🔧 Maintenance Commands

### **Restart Rock Pi Runner**
```bash
ssh github-runner@your-rock-pi-ip
sudo systemctl restart actions.runner.*
```

### **Update Runner**
```bash
# Stop runner
sudo ./svc.sh stop

# Download new version
curl -o actions-runner-linux-arm64-X.X.X.tar.gz -L [URL]

# Reconfigure and restart
./config.sh remove
./config.sh --url [REPO] --token [TOKEN]
sudo ./svc.sh install
sudo ./svc.sh start
```

### **Clean Up Test Artifacts**
```bash
# On Rock Pi
rm -rf /tmp/rockpi_test_*
rm -f /tmp/test_*.log
docker system prune -f  # if using Docker
```

---

## 📊 Monitoring & Alerts

### **Check System Health**
```bash
# Memory usage
free -h

# Disk space
df -h

# CPU/Temperature
htop
cat /sys/class/thermal/thermal_zone0/temp
```

### **Test Coverage Tracking**
- Coverage reports uploaded as artifacts
- Minimum 80% coverage required
- Critical tests require 95% coverage

### **Performance Baselines**
- Test duration tracking
- Memory usage monitoring
- Hardware interface response times

---

## 🚨 Troubleshooting

### **Runner Offline**
```bash
# Check network
ping github.com

# Restart runner service
sudo systemctl restart actions.runner.*

# Check logs
sudo journalctl -u actions.runner.* --since "1 hour ago"
```

### **Hardware Tests Failing**
```bash
# Check hardware interfaces
sudo systemctl status bluetooth
iwconfig
ls /sys/class/gpio/

# Verify permissions
groups github-runner
```

### **Out of Disk Space**
```bash
# Clean old artifacts
find /tmp -name "*.log" -mtime +7 -delete
docker system prune -af

# Check large files
du -h /home/github-runner | sort -hr | head -20
```

---

## 🎯 Best Practices

### **Pull Request Workflow**
1. Create feature branch
2. Make changes
3. Push → triggers PR validation
4. Address any failures quickly
5. Request review after all checks pass

### **Release Workflow**
1. Merge PR to main → triggers full CI/CD
2. Monitor hardware tests
3. Manual approval for production deployment
4. Deployment notifications sent

### **Emergency Procedures**
1. **Critical bug**: Hotfix branch → fast-track testing
2. **Runner down**: Use manual testing until restored
3. **System failure**: Have backup Rock Pi configured

---

## 📞 Quick Commands Reference

```bash
# Local test execution
python run_tests.py --critical                    # Critical tests only
python run_tests.py --category first_time_setup   # Specific category
python run_tests.py --scenario F1                 # Single scenario
python run_tests.py --hardware                    # Hardware-specific
python run_tests.py --coverage --report test.md   # With coverage report

# GitHub CLI (if installed)
gh workflow run ci-cd.yml                         # Trigger main workflow
gh run list --workflow=ci-cd.yml                  # List recent runs
gh run view [RUN_ID]                              # View specific run

# Runner management
sudo systemctl status actions.runner.*            # Check status
sudo systemctl restart actions.runner.*           # Restart runner
sudo journalctl -u actions.runner.* -f           # Follow logs
```

---

## 📈 Success Metrics

### **Quality Gates**
- ✅ All PR validations pass
- ✅ Code coverage ≥ 80%
- ✅ No security vulnerabilities
- ✅ Hardware tests pass on real devices

### **Performance Targets**
- PR feedback: < 5 minutes
- Hardware tests: < 30 minutes  
- Nightly tests: < 60 minutes
- Zero false positives

### **Reliability Metrics**
- 99%+ runner uptime
- < 1% test flakiness
- Automated recovery procedures
- Comprehensive monitoring

---

**Need help?** Check the full setup guide at `.github/SETUP_CI_CD.md` or create an issue! 🚀
