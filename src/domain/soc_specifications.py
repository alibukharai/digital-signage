"""
SOC Specifications - refactored into smaller, focused modules
This file provides backwards compatibility by re-exporting from the soc module
"""

# Import from the refactored module
from .soc.base_types import (
    SOCFamily, 
    ArchitectureType, 
    PerformanceProfile, 
    ConnectivityProfile, 
    IOProfile, 
    PowerProfile
)

# For now, maintain a simple specification class until full refactor
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SOCSpecification:
    """Complete SOC specification"""
    
    name: str
    family: SOCFamily
    architecture: ArchitectureType
    performance: PerformanceProfile
    connectivity: ConnectivityProfile
    io_capabilities: IOProfile
    power_management: PowerProfile
    detection_patterns: List[str]
    device_tree_compatible: List[str]
    
    def matches_hardware(self, hardware_info: Dict[str, Any]) -> bool:
        """Check if this specification matches the detected hardware"""
        try:
            model = hardware_info.get("model", "").lower()
            compatible = hardware_info.get("compatible", [])
            
            # Check device tree compatible strings
            for compat in self.device_tree_compatible:
                if any(compat in c for c in compatible):
                    return True
                    
            # Check detection patterns
            for pattern in self.detection_patterns:
                if pattern.lower() in model:
                    return True
                    
            return False
        except (AttributeError, TypeError):
            return False


# Simple SOC Manager for backwards compatibility
class SOCManager:
    """Simplified SOC manager for hardware detection and configuration"""
    
    def __init__(self):
        self._specifications: List[SOCSpecification] = []
        self._register_default_specs()
    
    def _register_default_specs(self):
        """Register default SOC specifications"""
        # Rock Pi 4B+ (OP1)
        self.register_specification(SOCSpecification(
            name="Rock Pi 4B+ (OP1)",
            family=SOCFamily.ROCKCHIP,
            architecture=ArchitectureType.ARM64,
            performance=PerformanceProfile(
                cpu_cores=6,
                cpu_big_cores=2,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=2000,
                cpu_little_max_freq_mhz=1500,
                memory_max_gb=4,
                memory_type="LPDDR4"
            ),
            connectivity=ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="5.0",
                ethernet_speeds=["1000"],
                hdmi_version="2.0",
                max_resolution="4K@60Hz"
            ),
            io_capabilities=IOProfile(
                gpio_pins=40,
                emmc_support=True,
                sd_card_support=True,
                nvme_support=True
            ),
            power_management=PowerProfile(
                poe_support=True,
                power_states=["active", "idle", "suspend"]
            ),
            detection_patterns=["rock-pi-4b-plus", "op1"],
            device_tree_compatible=["rockchip,rock-pi-4b-plus", "rockchip,op1"]
        ))
        
        # Rock Pi 4 (RK3399)
        self.register_specification(SOCSpecification(
            name="Rock Pi 4 (RK3399)",
            family=SOCFamily.ROCKCHIP,
            architecture=ArchitectureType.ARM64,
            performance=PerformanceProfile(
                cpu_cores=6,
                cpu_big_cores=2,
                cpu_little_cores=4,
                cpu_big_max_freq_mhz=1800,
                cpu_little_max_freq_mhz=1400,
                memory_max_gb=4,
                memory_type="LPDDR4"
            ),
            connectivity=ConnectivityProfile(
                wifi_standards=["802.11ac"],
                bluetooth_version="4.2",
                ethernet_speeds=["1000"],
                hdmi_version="2.0",
                max_resolution="4K@30Hz"
            ),
            io_capabilities=IOProfile(
                gpio_pins=40,
                emmc_support=True,
                sd_card_support=True
            ),
            power_management=PowerProfile(
                power_states=["active", "idle", "suspend"]
            ),
            detection_patterns=["rock-pi-4", "rk3399"],
            device_tree_compatible=["rockchip,rock-pi-4", "rockchip,rk3399"]
        ))
    
    def register_specification(self, spec: SOCSpecification):
        """Register a new SOC specification"""
        self._specifications.append(spec)
    
    def detect_soc(self, hardware_info: Optional[Dict[str, Any]] = None) -> Optional[SOCSpecification]:
        """Detect SOC based on hardware information"""
        if not hardware_info:
            hardware_info = self._get_hardware_info()
        
        for spec in self._specifications:
            if spec.matches_hardware(hardware_info):
                return spec
        
        return None
    
    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get hardware information from system"""
        try:
            import os
            import platform
            
            info = {
                "model": platform.machine(),
                "compatible": [],
                "processor": platform.processor()
            }
            
            # Try to read device tree compatible
            try:
                with open("/proc/device-tree/compatible", "r") as f:
                    compatible_str = f.read().strip("\x00")
                    info["compatible"] = compatible_str.split("\x00")
            except (FileNotFoundError, PermissionError):
                pass
                
            # Try to read model
            try:
                with open("/proc/device-tree/model", "r") as f:
                    info["model"] = f.read().strip("\x00")
            except (FileNotFoundError, PermissionError):
                pass
                
            return info
            
        except ImportError:
            return {"model": "unknown", "compatible": [], "processor": "unknown"}


# Create global instance for backwards compatibility
soc_manager = SOCManager()

# Re-export for backwards compatibility
__all__ = [
    "SOCFamily",
    "ArchitectureType", 
    "PerformanceProfile",
    "ConnectivityProfile",
    "IOProfile",
    "PowerProfile",
    "SOCSpecification",
    "SOCManager",
    "soc_manager"
]
