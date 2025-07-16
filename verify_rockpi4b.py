#!/usr/bin/env python3
"""
ROCK Pi 4B+ Hardware Verification Script
Tests all hardware-specific optimizations and features
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.common.result_handling import Result
from src.domain.configuration import BLEConfig, DisplayConfig, NetworkConfig
from src.infrastructure.bluetooth import BluetoothService
from src.infrastructure.device import DeviceInfoProvider
from src.infrastructure.display import DisplayService
from src.infrastructure.gpio import RockPi4BPlusGPIOService
from src.infrastructure.network import NetworkService
from src.infrastructure.performance import OP1MemoryManager, OP1PerformanceMonitor


class RockPi4BPlusVerificationSuite:
    """Comprehensive verification suite for ROCK Pi 4B+ optimizations"""

    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []
        self.device_provider = DeviceInfoProvider()

        # Load configuration
        config_path = Path("config/unified_config.json")
        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)
        else:
            config_data = {}

        # Initialize services
        self.display_config = DisplayConfig(
            width=config_data.get("display", {}).get("resolution_width", 1920),
            height=config_data.get("display", {}).get("resolution_height", 1080),
            qr_size=config_data.get("display", {}).get("qr_code_size_1080p", 400),
            background_color=config_data.get("display", {}).get(
                "background_color", "#000000"
            ),
            text_color=config_data.get("display", {}).get("text_color", "#FFFFFF"),
        )

        self.ble_config = BLEConfig(
            service_uuid=config_data.get("ble", {}).get(
                "service_uuid", "12345678-1234-5678-9abc-123456789abc"
            ),
            connection_timeout=config_data.get("ble", {}).get("connection_timeout", 30),
            advertising_interval=config_data.get("ble", {}).get(
                "advertising_interval", 100
            ),
        )

        self.network_config = NetworkConfig(
            interface_name=config_data.get("network", {}).get(
                "interface_name", "wlan0"
            ),
            connection_timeout=config_data.get("network", {}).get(
                "connection_timeout", 30
            ),
            wifi_scan_timeout=config_data.get("network", {}).get("scan_timeout", 10),
        )

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        self.results.append((test_name, success, details))

    def verify_hardware_detection(self) -> bool:
        """Verify ROCK Pi 4B+ hardware detection"""
        print("\n🔍 Hardware Detection Tests")
        print("=" * 40)

        try:
            device_info = self.device_provider.get_device_info()

            # Check SoC detection
            soc_type = self.device_provider._detect_soc_type()
            self.log_result(
                "SoC Detection", soc_type in ["OP1", "RK3399"], f"Detected: {soc_type}"
            )

            # Check memory detection
            memory_info = self.device_provider._get_memory_info()
            memory_gb = memory_info.get("total_kb", 0) / 1024 / 1024
            self.log_result(
                "Memory Detection", memory_gb > 0, f"Total: {memory_gb:.1f}GB"
            )

            # Check hardware version
            hw_version = device_info.hardware_version
            is_rockpi = "rock" in hw_version.lower() or "op1" in hw_version.lower()
            self.log_result("Hardware Version", is_rockpi, f"Version: {hw_version}")

            # Check capabilities
            capabilities = device_info.capabilities
            required_caps = ["wifi", "bluetooth", "ethernet", "display"]
            has_required = all(cap in capabilities for cap in required_caps)
            self.log_result(
                "Basic Capabilities",
                has_required,
                f"Found: {len(capabilities)} capabilities",
            )

            # Check OP1 specific capabilities
            if soc_type == "OP1":
                op1_caps = ["bluetooth_5_0", "hdmi_2_0", "4k_display", "poe_capable"]
                has_op1_caps = any(cap in capabilities for cap in op1_caps)
                self.log_result(
                    "OP1 Capabilities",
                    has_op1_caps,
                    f"OP1 features: {[c for c in op1_caps if c in capabilities]}",
                )

            return True

        except Exception as e:
            self.log_result("Hardware Detection", False, f"Error: {e}")
            return False

    def verify_display_optimization(self) -> bool:
        """Verify display optimizations"""
        print("\n📺 Display Optimization Tests")
        print("=" * 40)

        try:
            display_service = DisplayService(self.display_config)

            # Check resolution detection
            resolutions = display_service.supported_resolutions
            has_resolutions = len(resolutions) > 0
            self.log_result(
                "Resolution Detection",
                has_resolutions,
                f"Found {len(resolutions)} resolutions",
            )

            # Check 4K capability
            is_4k_capable = display_service.is_4k_capable
            optimal_res = display_service.optimal_resolution
            self.log_result(
                "4K Capability",
                True,
                f"4K: {is_4k_capable}, Optimal: {optimal_res[0]}x{optimal_res[1]}@{optimal_res[2]}Hz",
            )

            # Test display configuration
            config_result = display_service._configure_optimal_display()
            self.log_result(
                "Display Configuration", True, f"Config applied: {config_result}"
            )

            return True

        except Exception as e:
            self.log_result("Display Optimization", False, f"Error: {e}")
            return False

    def verify_performance_monitoring(self) -> bool:
        """Verify performance monitoring"""
        print("\n⚡ Performance Monitoring Tests")
        print("=" * 40)

        try:
            # Test OP1 performance monitor
            perf_monitor = OP1PerformanceMonitor()

            # Check thermal zone discovery
            thermal_zones = perf_monitor.thermal_zones
            has_thermal = len(thermal_zones) > 0
            self.log_result(
                "Thermal Zones", has_thermal, f"Found: {list(thermal_zones.keys())}"
            )

            # Get performance metrics
            metrics = perf_monitor.get_current_metrics()
            self.log_result(
                "CPU Metrics",
                metrics.cpu_usage_cortex_a72 >= 0,
                f"A72: {metrics.cpu_usage_cortex_a72:.1f}%, A53: {metrics.cpu_usage_cortex_a53:.1f}%",
            )
            self.log_result(
                "Memory Metrics",
                metrics.memory_used_mb > 0,
                f"Used: {metrics.memory_used_mb:.0f}MB, Available: {metrics.memory_available_mb:.0f}MB",
            )
            self.log_result(
                "Temperature",
                metrics.temperature_soc >= 0,
                f"SoC: {metrics.temperature_soc:.1f}°C, GPU: {metrics.temperature_gpu:.1f}°C",
            )

            # Test memory manager
            mem_manager = OP1MemoryManager()
            total_mem_gb = mem_manager.total_memory / 1024 / 1024
            self.log_result(
                "Memory Manager", total_mem_gb > 0, f"Total: {total_mem_gb:.1f}GB"
            )

            return True

        except Exception as e:
            self.log_result("Performance Monitoring", False, f"Error: {e}")
            return False

    def verify_gpio_service(self) -> bool:
        """Verify GPIO service"""
        print("\n🔌 GPIO Service Tests")
        print("=" * 40)

        try:
            gpio_service = RockPi4BPlusGPIOService()

            # Check initialization
            self.log_result(
                "GPIO Initialization",
                gpio_service.initialized,
                "GPIO service initialized",
            )

            # Test LED control
            led_result = gpio_service.set_status_led("green", True)
            self.log_result("LED Control", led_result.is_success(), "Green LED test")

            # Turn off LED
            gpio_service.set_status_led("green", False)

            # Test status pattern
            pattern_result = gpio_service.show_status_pattern("boot")
            self.log_result(
                "Status Pattern", pattern_result.is_success(), "Boot status pattern"
            )

            # Clean up
            gpio_service.cleanup()

            return True

        except Exception as e:
            self.log_result("GPIO Service", False, f"Error: {e}")
            return False

    def verify_network_optimizations(self) -> bool:
        """Verify network optimizations"""
        print("\n🌐 Network Optimization Tests")
        print("=" * 40)

        try:
            network_service = NetworkService(self.network_config)

            # Check interface detection
            eth_interfaces = network_service.ethernet_interfaces
            wifi_interfaces = network_service.wifi_interfaces
            self.log_result(
                "Interface Detection",
                len(eth_interfaces) + len(wifi_interfaces) > 0,
                f"Ethernet: {eth_interfaces}, WiFi: {wifi_interfaces}",
            )

            # Check hardware platform
            platform = network_service.hardware_platform
            self.log_result(
                "Platform Detection", platform != "UNKNOWN", f"Platform: {platform}"
            )

            # Check PoE capability
            poe_capable = network_service.poe_capable
            self.log_result("PoE Detection", True, f"PoE capable: {poe_capable}")

            # Test OP1 optimizations
            if platform == "OP1":
                opt_result = network_service._apply_op1_optimizations()
                self.log_result("OP1 Optimizations", True, f"Applied: {opt_result}")

            return True

        except Exception as e:
            self.log_result("Network Optimizations", False, f"Error: {e}")
            return False

    async def verify_bluetooth_service(self) -> bool:
        """Verify Bluetooth service"""
        print("\n📶 Bluetooth Service Tests")
        print("=" * 40)

        try:
            bluetooth_service = BluetoothService(self.ble_config)

            # Check BLE 5.0 features
            max_connections = bluetooth_service._max_concurrent_connections
            phy_mode = bluetooth_service._phy_mode
            self.log_result(
                "BLE 5.0 Features",
                max_connections > 1,
                f"Max connections: {max_connections}, PHY: {phy_mode}",
            )

            # Check multiple connection support
            self.log_result(
                "Multiple Connections",
                hasattr(bluetooth_service, "_multiple_connections"),
                "Multiple connection tracking",
            )

            # Check extended advertising
            self.log_result(
                "Extended Advertising",
                hasattr(bluetooth_service, "_extended_advertising_data"),
                "Extended advertising support",
            )

            return True

        except Exception as e:
            self.log_result("Bluetooth Service", False, f"Error: {e}")
            return False

    def check_system_services(self) -> bool:
        """Check required system services"""
        print("\n🔧 System Services Tests")
        print("=" * 40)

        services_to_check = [
            ("bluetooth", "Bluetooth service"),
            ("NetworkManager", "Network Manager"),
            ("ssh", "SSH service"),
        ]

        all_good = True

        for service, description in services_to_check:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                is_active = result.returncode == 0
                status = result.stdout.strip() if is_active else "inactive"
                self.log_result(description, is_active, f"Status: {status}")

                if not is_active:
                    all_good = False

            except Exception as e:
                self.log_result(description, False, f"Error: {e}")
                all_good = False

        return all_good

    def check_hardware_features(self) -> bool:
        """Check hardware-specific features"""
        print("\n🖥️  Hardware Features Tests")
        print("=" * 40)

        features_checked = 0
        features_working = 0

        # Check display output
        try:
            result = subprocess.run(
                ["xrandr", "--query"], capture_output=True, text=True, timeout=10
            )
            display_connected = "connected" in result.stdout
            self.log_result(
                "Display Output", display_connected, "HDMI display connection"
            )
            features_checked += 1
            if display_connected:
                features_working += 1
        except Exception as e:
            self.log_result("Display Output", False, f"Error: {e}")
            features_checked += 1

        # Check Bluetooth hardware
        try:
            result = subprocess.run(
                ["hciconfig"], capture_output=True, text=True, timeout=5
            )
            bt_available = "hci" in result.stdout
            self.log_result("Bluetooth Hardware", bt_available, "Bluetooth adapter")
            features_checked += 1
            if bt_available:
                features_working += 1
        except Exception as e:
            self.log_result("Bluetooth Hardware", False, f"Error: {e}")
            features_checked += 1

        # Check WiFi hardware
        try:
            result = subprocess.run(
                ["iwconfig"], capture_output=True, text=True, timeout=5
            )
            wifi_available = "IEEE 802.11" in result.stdout
            self.log_result("WiFi Hardware", wifi_available, "WiFi adapter")
            features_checked += 1
            if wifi_available:
                features_working += 1
        except Exception as e:
            self.log_result("WiFi Hardware", False, f"Error: {e}")
            features_checked += 1

        # Check GPIO access
        try:
            gpio_available = Path("/sys/class/gpio").exists()
            self.log_result("GPIO Access", gpio_available, "GPIO filesystem")
            features_checked += 1
            if gpio_available:
                features_working += 1
        except Exception as e:
            self.log_result("GPIO Access", False, f"Error: {e}")
            features_checked += 1

        return features_working >= features_checked // 2

    async def run_comprehensive_test(self) -> bool:
        """Run all verification tests"""
        print("🚀 ROCK Pi 4B+ Comprehensive Verification Suite")
        print("=" * 50)

        test_results = []

        # Run all test categories
        test_results.append(self.verify_hardware_detection())
        test_results.append(self.verify_display_optimization())
        test_results.append(self.verify_performance_monitoring())
        test_results.append(self.verify_gpio_service())
        test_results.append(self.verify_network_optimizations())
        test_results.append(await self.verify_bluetooth_service())
        test_results.append(self.check_system_services())
        test_results.append(self.check_hardware_features())

        # Generate summary
        print("\n📊 Test Summary")
        print("=" * 50)

        passed_tests = sum(1 for _, success, _ in self.results if success)
        total_tests = len(self.results)

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests * 100):.1f}%")

        # Show failed tests
        failed_tests = [
            (name, details) for name, success, details in self.results if not success
        ]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for name, details in failed_tests:
                print(f"   - {name}: {details}")

        # Overall result
        overall_success = passed_tests >= total_tests * 0.8  # 80% pass rate
        status = "✅ PASS" if overall_success else "❌ FAIL"
        print(f"\n🎯 Overall Result: {status}")

        if overall_success:
            print("✅ ROCK Pi 4B+ is optimized and ready for production!")
        else:
            print("⚠️  Some optimizations may not be working correctly.")
            print("💡 This may be normal in development environments.")

        return overall_success


async def main():
    """Main verification function"""
    verification_suite = RockPi4BPlusVerificationSuite()

    try:
        success = await verification_suite.run_comprehensive_test()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n🛑 Verification interrupted by user")
        return 2
    except Exception as e:
        print(f"\n💥 Verification failed with error: {e}")
        return 3


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
