#!/bin/bash

# Setup script for development environment
# Run this once after cloning the repository

set -e

echo "🚀 Setting up Rock Pi 3399 Provisioning System development environment..."

# Check if Python 3.8+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "🐍 Using Python $PYTHON_VERSION"

# Install the package in development mode
echo "📦 Installing package in development mode..."
pip3 install -e ".[dev]"

# Install pre-commit hooks
echo "🎣 Setting up pre-commit hooks..."
pip3 install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg

# Run pre-commit on all files to verify setup
echo "🔍 Running pre-commit checks on all files..."
pre-commit run --all-files || {
    echo "⚠️ Some pre-commit checks failed. This is normal for initial setup."
    echo "💡 Fix the issues and run: pre-commit run --all-files"
}

# Verify test suite
echo "📋 Validating test suite..."
python validate_tests.py

# Run a quick test to verify everything works
echo "🧪 Running quick tests to verify setup..."
python -m pytest tests/ -m "not hardware and not integration and not slow" -x -q --tb=no || {
    echo "⚠️ Some tests failed. This might be normal if hardware is not available."
}

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Make code changes"
echo "  2. Commit your changes (pre-commit hooks will run automatically)"
echo "  3. Push to GitHub (CI/CD will run optimized workflows)"
echo ""
echo "🔧 Useful commands:"
echo "  - Run tests: python run_tests.py --quick"
echo "  - Format code: black src/ tests/"
echo "  - Check code: pre-commit run --all-files"
echo "  - Manual pre-commit: pre-commit run <hook-name>"
echo ""
echo "📊 GitHub Actions usage tips:"
echo "  - Use draft PRs to avoid running workflows while developing"
echo "  - Only push to main when ready for full testing"
echo "  - Use manual workflow dispatch for heavy testing"
