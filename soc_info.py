#!/usr/bin/env python3
"""
SOC Detection and Information Tool
Demonstrates the dynamic SOC detection capabilities
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.domain.configuration_factory import ConfigurationFactory
from src.domain.soc_registry import soc_registry
from src.domain.soc_specifications import soc_manager
from src.infrastructure.hardware_abstraction import HALFactory


def main():
    print("🔍 SOC Detection and Information Tool")
    print("=" * 50)

    # Detect current SOC
    print("\n1. SOC Detection:")
    soc_spec = soc_manager.detect_soc()

    if soc_spec:
        print(f"   ✅ Detected SOC: {soc_spec.name}")
        print(f"   📱 Family: {soc_spec.family.value}")
        print(f"   🏭 Manufacturer: {soc_spec.manufacturer}")
        print(f"   🏗️ Architecture: {soc_spec.architecture.value}")
        print(f"   ⚡ CPU Cores: {soc_spec.performance.cpu_cores}")
        print(f"   💾 Max Memory: {soc_spec.performance.memory_max_gb}GB")
        print(f"   📶 Bluetooth: {soc_spec.connectivity.bluetooth_version}")
        print(f"   📺 Max Resolution: {soc_spec.connectivity.max_resolution}")
        print(f"   🔌 GPIO Pins: {soc_spec.io.gpio_pins}")
    else:
        print("   ⚠️ No specific SOC detected (using generic fallback)")
        return

    # Show all supported SOCs
    print("\n2. Supported SOC Families:")
    for family in soc_registry.get_all_families():
        entry = soc_registry.get_family_info(family)
        print(f"   📋 {family.value.upper()}: {entry.description}")
        print(f"      🏭 {entry.manufacturer}")
        print(f"      🔧 Common boards: {', '.join(entry.common_boards[:3])}...")

    # Test HAL
    print("\n3. Hardware Abstraction Layer:")
    hal = HALFactory.create_hal(soc_spec)
    hal_result = hal.initialize()

    if hal_result.is_success():
        print(f"   ✅ HAL initialized: {hal.__class__.__name__}")
        capabilities = hal.get_capabilities()
        print(f"   🔌 GPIO Available: {capabilities.gpio_available}")
        print(f"   📡 I2C Available: {capabilities.i2c_available}")
        print(f"   🌐 WiFi Available: {capabilities.wifi_available}")
        print(f"   🔵 Bluetooth Available: {capabilities.bluetooth_available}")

        # Show GPIO mapping
        gpio_mapping = hal.get_gpio_mapping()
        print(f"   📍 GPIO Pins configured: {len(gpio_mapping)}")
        key_pins = ["status_led_green", "reset_button", "config_button"]
        for pin_name in key_pins:
            if pin_name in gpio_mapping:
                print(f"      {pin_name}: Pin {gpio_mapping[pin_name]}")
    else:
        print(f"   ❌ HAL initialization failed: {hal_result.error}")

    # Test Configuration
    print("\n4. Dynamic Configuration:")
    factory = ConfigurationFactory()
    config = factory.create_default()

    print(f"   📱 Device Name: {config.ble.device_name}")
    print(f"   🌐 Network Interface: {config.network.interface_name}")
    print(f"   📺 Display Size: {config.display.width}x{config.display.height}")
    print(f"   🔄 Health Check Interval: {config.system.health_check_interval}s")
    print(f"   📶 BLE Advertising Interval: {config.ble.advertising_interval}ms")

    # Show optimization details
    print("\n5. SOC-Specific Optimizations Applied:")
    if soc_spec.performance.cpu_cores >= 6:
        print("   ⚡ Big.LITTLE CPU optimization enabled")
    if "5.0" in soc_spec.connectivity.bluetooth_version:
        print("   📶 Bluetooth 5.0 fast advertising enabled")
    if "802.11ac" in soc_spec.connectivity.wifi_standards:
        print("   📡 WiFi 802.11ac fast scanning enabled")
    if "4K" in soc_spec.connectivity.max_resolution:
        print("   📺 4K display optimizations enabled")
    if soc_spec.power.poe_support:
        print("   🔌 PoE power management optimizations enabled")

    print("\n✅ SOC detection and configuration completed successfully!")

    # Show extensibility information
    print("\n6. Extensibility Information:")
    total_socs = len(soc_manager.get_all_supported_socs())
    print(f"   📊 Total supported SOCs: {total_socs}")
    print(f"   🏗️ Registered families: {len(soc_registry.get_all_families())}")
    print("   ➕ To add new SOC support:")
    print("      1. Create detector class inheriting from SOCDetector")
    print("      2. Register using register_custom_soc_family()")
    print("      3. Optionally create custom HAL for optimizations")
    print("   📖 See SOC_EXTENSIBILITY_GUIDE.md for details")


if __name__ == "__main__":
    main()
