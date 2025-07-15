#!/usr/bin/env python3
"""
Installation verification script for Rock Pi 3399 Provisioning System
"""

import importlib
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check Python version"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version >= (3, 8):
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(
            f"   ❌ Python {version.major}.{version.minor}.{version.micro} (Minimum 3.8 required)"
        )
        return False


def check_package_imports():
    """Check if package can be imported"""
    print("\n📦 Checking package imports...")

    try:
        # Test new architecture imports
        from src.interfaces import IBluetoothService, ILogger, INetworkService

        print("   ✅ Interface module imports (OK)")

        from src.domain.configuration import load_config

        print("   ✅ Domain module imports (OK)")

        from src.infrastructure import LoggingService, NetworkService

        print("   ✅ Infrastructure module imports (OK)")

        from src.application.dependency_injection import Container

        print("   ✅ Application module imports (OK)")

        return True
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False


def check_system_dependencies():
    """Check system dependencies"""
    print("\n🔧 Checking system dependencies...")

    dependencies = [
        ("hciconfig", "bluetooth"),
        ("iwconfig", "wireless-tools"),
        ("ip", "iproute2"),
    ]

    all_ok = True
    for cmd, package in dependencies:
        try:
            result = subprocess.run(["which", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ {cmd} found")
            else:
                print(f"   ⚠️  {cmd} not found (install {package})")
                all_ok = False
        except Exception as e:
            print(f"   ❌ Error checking {cmd}: {e}")
            all_ok = False

    return all_ok


def check_configuration():
    """Check configuration loading"""
    print("\n⚙️  Checking configuration...")

    try:
        from src.domain.configuration import load_config

        config = load_config()
        print("   ✅ Configuration loads successfully")

        # Check key configuration sections
        if hasattr(config, "ble") and hasattr(config, "network"):
            print("   ✅ Configuration sections present")
            return True
        else:
            print("   ⚠️  Some configuration sections missing")
            return False

    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        return False


def check_service_files():
    """Check if service files exist"""
    print("\n🔧 Checking installation files...")

    files_to_check = [
        ("/etc/systemd/system/rock-provisioning.service", "SystemD service"),
        ("venv/bin/python", "Virtual environment"),
        ("src", "Source directory"),
    ]

    all_ok = True
    for file_path, description in files_to_check:
        path = Path(file_path)
        if path.exists():
            print(f"   ✅ {description} exists")
        else:
            print(f"   ⚠️  {description} not found at {file_path}")
            all_ok = False

    return all_ok


def check_architecture():
    """Check new architecture components"""
    print("\n🏗️  Checking architecture components...")

    try:
        # Test core services can be created
        from src.application.dependency_injection import Container
        from src.domain.configuration import load_config
        from src.infrastructure import LoggingService

        config = load_config()
        logger = LoggingService(config.logging)
        container = Container()

        print("   ✅ Core services can be instantiated")

        # Test DI container
        from src.interfaces import ILogger

        container.register_instance(ILogger, logger)
        resolved = container.resolve(ILogger)

        print("   ✅ Dependency injection working")
        return True

    except Exception as e:
        print(f"   ❌ Architecture check failed: {e}")
        return False


def main():
    """Main verification function"""
    print("🔍 Rock Pi 3399 Provisioning System - Installation Verification")
    print("=" * 70)

    checks = [
        ("Python Version", check_python_version),
        ("Package Imports", check_package_imports),
        ("System Dependencies", check_system_dependencies),
        ("Configuration", check_configuration),
        ("Installation Files", check_service_files),
        ("Architecture", check_architecture),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Error during {name} check: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("📋 Verification Summary:")
    print("=" * 70)

    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
        if result:
            passed += 1

    print(f"\n🎯 Result: {passed}/{len(results)} checks passed")

    if passed == len(results):
        print("\n✅ Installation verification completed successfully!")
        print("   You can now start the service with: make run")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review the issues above.")
        print("   Try running: make install")
        return 1


if __name__ == "__main__":
    sys.exit(main())
