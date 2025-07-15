# Rock Pi 3399 Provisioning System Makefile

# Python settings
PYTHON := python3
VENV_PATH := venv
PIP := $(VENV_PATH)/bin/pip
PYTHON_VENV := $(VENV_PATH)/bin/python

# Project settings
PROJECT_NAME := rock-provisioning
SERVICE_NAME := rock-provisioning.service
CONFIG_DIR := /etc/rockpi-provisioning
LOG_DIR := logs

.PHONY: help install uninstall test run dev clean lint format check status logs requirements

# Default target
help:
	@echo "Rock Pi 3399 Provisioning System"
	@echo "================================="
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install system dependencies and setup environment"
	@echo "  uninstall   - Remove installed files and services"
	@echo "  test        - Run tests and verify installation"
	@echo "  run         - Run the provisioning system"
	@echo "  dev         - Run in development mode"
	@echo "  clean       - Clean build artifacts and logs"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code"
	@echo "  check       - Run all checks (lint + test)"
	@echo "  status      - Show system status"
	@echo "  logs        - Show system logs"
	@echo "  deps       - Install dependencies from pyproject.toml"

# Install system dependencies and setup environment
install:
	@echo "🚀 Installing Rock Pi 3399 Provisioning System..."
	chmod +x install.sh
	./install.sh
	@echo "✅ Installation complete! Run 'make test' to verify."

# Remove installed files and services
uninstall:
	@echo "🗑️  Uninstalling Rock Pi 3399 Provisioning System..."
	sudo systemctl stop $(SERVICE_NAME) || true
	sudo systemctl disable $(SERVICE_NAME) || true
	sudo rm -f /etc/systemd/system/$(SERVICE_NAME)
	sudo rm -rf $(CONFIG_DIR)
	sudo systemctl daemon-reload
	@echo "✅ Uninstall complete!"

# Run tests and verify installation
test:
	@echo "🧪 Running tests and verification..."
	PYTHONPATH=. $(PYTHON) scripts/verify_installation.py
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		echo "🔍 Testing package imports..."; \
		PYTHONPATH=. $(PYTHON_VENV) -c "from src.application.dependency_injection import Container; print('✅ All imports successful')"; \
	else \
		echo "🔍 Testing package imports..."; \
		PYTHONPATH=. $(PYTHON) -c "from src.application.dependency_injection import Container; print('✅ All imports successful')"; \
	fi

# Run the provisioning system
run:
	@echo "🚀 Starting Rock Pi 3399 Provisioning System..."
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		PYTHONPATH=. $(PYTHON_VENV) -m src; \
	else \
		PYTHONPATH=. $(PYTHON) -m src; \
	fi

# Run in development mode
dev:
	@echo "🔧 Starting in development mode..."
	@mkdir -p $(LOG_DIR)
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		PYTHONPATH=. $(PYTHON_VENV) -m src --dev; \
	else \
		PYTHONPATH=. $(PYTHON) -m src --dev; \
	fi

# Clean build artifacts and logs
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# Run code linting
lint:
	@echo "🔍 Running code linting..."
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		$(PIP) install --quiet flake8 pylint || true; \
		$(VENV_PATH)/bin/flake8 src/ --max-line-length=100 --ignore=E203,W503 || true; \
		$(VENV_PATH)/bin/pylint src/ --disable=C0111,R0903 || true; \
	else \
		echo "⚠️  Virtual environment not found, skipping lint"; \
	fi

# Format code
format:
	@echo "✨ Formatting code..."
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		$(PIP) install --quiet black isort || true; \
		$(VENV_PATH)/bin/black src/ --line-length=100 || true; \
		$(VENV_PATH)/bin/isort src/ --profile black || true; \
	else \
		echo "⚠️  Virtual environment not found, skipping format"; \
	fi

# Run all checks
check: lint test
	@echo "✅ All checks complete!"

# Show system status
status:
	@echo "📊 System Status"
	@echo "================"
	@echo "Service Status:"
	@systemctl is-active $(SERVICE_NAME) 2>/dev/null || echo "  Service not running"
	@echo ""
	@echo "Python Environment:"
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		echo "  ✅ Virtual environment: $(VENV_PATH)"; \
		$(PYTHON_VENV) --version; \
	else \
		echo "  ⚠️  No virtual environment found"; \
		$(PYTHON) --version; \
	fi
	@echo ""
	@echo "Configuration:"
	@if [ -f "config/unified_config.json" ]; then \
		echo "  ✅ Development config: config/unified_config.json"; \
	fi
	@if [ -f "$(CONFIG_DIR)/config.json" ]; then \
		echo "  ✅ Production config: $(CONFIG_DIR)/config.json"; \
	fi

# Show system logs
logs:
	@echo "📋 Recent Logs"
	@echo "=============="
	@if [ -f "$(LOG_DIR)/rockpi-provisioning.log" ]; then \
		tail -50 $(LOG_DIR)/rockpi-provisioning.log; \
	else \
		echo "No local log file found"; \
	fi
	@echo ""
	@echo "System service logs:"
	@journalctl -u $(SERVICE_NAME) --no-pager -n 20 2>/dev/null || echo "Service not found in journalctl"

# Install dependencies from pyproject.toml
deps:
	@echo "📦 Installing dependencies from pyproject.toml..."
	@if [ -f "$(VENV_PATH)/bin/python" ]; then \
		$(PIP) install -e ".[dev]"; \
		echo "✅ Dependencies installed successfully"; \
	else \
		echo "⚠️  Virtual environment not found, installing globally"; \
		pip install -e ".[dev]"; \
	fi
