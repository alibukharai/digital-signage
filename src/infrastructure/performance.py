"""
Performance monitoring service optimized for ROCK Pi 4B+ with OP1 processor
"""

import asyncio
import glob
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import psutil

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..interfaces import ILogger


@dataclass
class OP1PerformanceMetrics:
    """Performance metrics specific to OP1 architecture"""

    timestamp: float
    cpu_usage_cortex_a72: float  # Big cores
    cpu_usage_cortex_a53: float  # Little cores
    cpu_frequency_big: float
    cpu_frequency_little: float
    memory_used_mb: float
    memory_available_mb: float
    memory_cached_mb: float
    temperature_soc: float
    temperature_gpu: float
    gpu_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    storage_read_mb: float
    storage_write_mb: float
    power_consumption_mw: Optional[float] = None


class OP1PerformanceMonitor:
    """Performance monitoring optimized for OP1 processor"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.baseline_metrics = None
        self.thermal_zones = self._discover_thermal_zones()
        self._monitoring = False
        self._monitor_task = None

    def _discover_thermal_zones(self) -> Dict[str, str]:
        """Discover OP1 thermal zones"""
        thermal_zones = {}
        try:
            zone_mappings = {
                "soc": ["soc-thermal", "cpu-thermal", "rockchip-thermal"],
                "gpu": ["gpu-thermal", "mali-thermal"],
                "wifi": ["wifi-thermal"],
            }

            for zone_type, possible_names in zone_mappings.items():
                for name in possible_names:
                    thermal_path = "/sys/class/thermal/thermal_zone*/type"
                    for path in glob.glob(thermal_path):
                        try:
                            with open(path, "r") as f:
                                if f.read().strip() == name:
                                    zone_dir = path.replace("/type", "")
                                    thermal_zones[zone_type] = f"{zone_dir}/temp"
                                    break
                        except Exception:
                            continue
                    if zone_type in thermal_zones:
                        break

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Thermal zone discovery failed: {e}")

        return thermal_zones

    def get_current_metrics(self) -> OP1PerformanceMetrics:
        """Get current performance metrics"""
        try:
            # CPU metrics with core differentiation
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)

            # Assume first 2 cores are Cortex-A72, rest are Cortex-A53
            big_cores = cpu_percent[:2] if len(cpu_percent) >= 2 else [0, 0]
            little_cores = cpu_percent[2:] if len(cpu_percent) > 2 else [0, 0, 0, 0]

            cpu_usage_a72 = sum(big_cores) / len(big_cores)
            cpu_usage_a53 = sum(little_cores) / len(little_cores)

            # CPU frequencies
            cpu_freq = psutil.cpu_freq(percpu=True)
            freq_big = cpu_freq[0].current if cpu_freq else 0
            freq_little = cpu_freq[2].current if len(cpu_freq) > 2 else 0

            # Memory metrics
            memory = psutil.virtual_memory()

            # Temperature readings
            temp_soc = self._read_temperature("soc")
            temp_gpu = self._read_temperature("gpu")

            # GPU usage (if available)
            gpu_usage = self._get_gpu_usage()

            # Network stats
            net_io = psutil.net_io_counters()

            # Storage stats
            disk_io = psutil.disk_io_counters()

            return OP1PerformanceMetrics(
                timestamp=time.time(),
                cpu_usage_cortex_a72=cpu_usage_a72,
                cpu_usage_cortex_a53=cpu_usage_a53,
                cpu_frequency_big=freq_big,
                cpu_frequency_little=freq_little,
                memory_used_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                memory_cached_mb=memory.cached / 1024 / 1024,
                temperature_soc=temp_soc,
                temperature_gpu=temp_gpu,
                gpu_usage_percent=gpu_usage,
                network_bytes_sent=net_io.bytes_sent,
                network_bytes_recv=net_io.bytes_recv,
                storage_read_mb=disk_io.read_bytes / 1024 / 1024,
                storage_write_mb=disk_io.write_bytes / 1024 / 1024,
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Performance metrics collection failed: {e}")
            return OP1PerformanceMetrics(
                timestamp=time.time(),
                cpu_usage_cortex_a72=0,
                cpu_usage_cortex_a53=0,
                cpu_frequency_big=0,
                cpu_frequency_little=0,
                memory_used_mb=0,
                memory_available_mb=0,
                memory_cached_mb=0,
                temperature_soc=0,
                temperature_gpu=0,
                gpu_usage_percent=0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                storage_read_mb=0,
                storage_write_mb=0,
            )

    def _read_temperature(self, zone: str) -> float:
        """Read temperature from thermal zone"""
        thermal_path = self.thermal_zones.get(zone)
        if thermal_path:
            try:
                with open(thermal_path, "r") as f:
                    return float(f.read().strip()) / 1000.0  # Convert millicelsius
            except Exception:
                pass
        return 0.0

    def _get_gpu_usage(self) -> float:
        """Get GPU usage percentage for Mali-T860MP4"""
        try:
            # Try to read Mali GPU utilization
            gpu_paths = [
                "/sys/class/misc/mali0/device/utilization",
                "/sys/devices/platform/ff9a0000.gpu/utilization",
                "/sys/kernel/debug/mali/utilization",
            ]

            for path in gpu_paths:
                try:
                    with open(path, "r") as f:
                        content = f.read().strip()
                        # Parse utilization (may be in different formats)
                        if "%" in content:
                            return float(content.replace("%", ""))
                        else:
                            return float(content)
                except FileNotFoundError:
                    continue

        except Exception:
            pass
        return 0.0

    async def start_monitoring(self, interval: float = 5.0) -> Result[bool, Exception]:
        """Start continuous performance monitoring"""
        try:
            if self._monitoring:
                return Result.success(True)

            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop(interval))

            if self.logger:
                self.logger.info(
                    f"Started OP1 performance monitoring (interval: {interval}s)"
                )

            return Result.success(True)

        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_ERROR,
                    f"Failed to start performance monitoring: {e}",
                    ErrorSeverity.MEDIUM,
                )
            )

    async def stop_monitoring(self) -> Result[bool, Exception]:
        """Stop performance monitoring"""
        try:
            self._monitoring = False

            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            if self.logger:
                self.logger.info("Stopped OP1 performance monitoring")

            return Result.success(True)

        except Exception as e:
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_ERROR,
                    f"Failed to stop performance monitoring: {e}",
                    ErrorSeverity.LOW,
                )
            )

    async def _monitoring_loop(self, interval: float) -> None:
        """Continuous monitoring loop"""
        while self._monitoring:
            try:
                metrics = self.get_current_metrics()

                # Log performance warnings
                self._check_performance_thresholds(metrics)

                # Store baseline on first run
                if self.baseline_metrics is None:
                    self.baseline_metrics = metrics

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Monitoring loop error: {e}")
                await asyncio.sleep(interval)

    def _check_performance_thresholds(self, metrics: OP1PerformanceMetrics) -> None:
        """Check performance thresholds and log warnings"""
        try:
            # Temperature warnings
            if metrics.temperature_soc > 80:
                if self.logger:
                    self.logger.warning(
                        f"High SoC temperature: {metrics.temperature_soc:.1f}°C"
                    )

            if metrics.temperature_gpu > 85:
                if self.logger:
                    self.logger.warning(
                        f"High GPU temperature: {metrics.temperature_gpu:.1f}°C"
                    )

            # CPU usage warnings
            if metrics.cpu_usage_cortex_a72 > 90:
                if self.logger:
                    self.logger.warning(
                        f"High Cortex-A72 usage: {metrics.cpu_usage_cortex_a72:.1f}%"
                    )

            # Memory warnings
            memory_usage_percent = (
                metrics.memory_used_mb
                / (metrics.memory_used_mb + metrics.memory_available_mb)
            ) * 100
            if memory_usage_percent > 85:
                if self.logger:
                    self.logger.warning(
                        f"High memory usage: {memory_usage_percent:.1f}%"
                    )

        except Exception as e:
            if self.logger:
                self.logger.debug(f"Threshold check error: {e}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for reporting"""
        try:
            current_metrics = self.get_current_metrics()

            return {
                "hardware": "ROCK Pi 4B+ (OP1)",
                "timestamp": current_metrics.timestamp,
                "cpu": {
                    "big_cores_usage": current_metrics.cpu_usage_cortex_a72,
                    "little_cores_usage": current_metrics.cpu_usage_cortex_a53,
                    "big_cores_freq_mhz": current_metrics.cpu_frequency_big,
                    "little_cores_freq_mhz": current_metrics.cpu_frequency_little,
                },
                "memory": {
                    "used_mb": current_metrics.memory_used_mb,
                    "available_mb": current_metrics.memory_available_mb,
                    "cached_mb": current_metrics.memory_cached_mb,
                    "usage_percent": round(
                        (
                            current_metrics.memory_used_mb
                            / (
                                current_metrics.memory_used_mb
                                + current_metrics.memory_available_mb
                            )
                        )
                        * 100,
                        1,
                    ),
                },
                "temperature": {
                    "soc_celsius": current_metrics.temperature_soc,
                    "gpu_celsius": current_metrics.temperature_gpu,
                },
                "gpu": {"usage_percent": current_metrics.gpu_usage_percent},
                "network": {
                    "bytes_sent": current_metrics.network_bytes_sent,
                    "bytes_received": current_metrics.network_bytes_recv,
                },
                "storage": {
                    "read_mb": current_metrics.storage_read_mb,
                    "write_mb": current_metrics.storage_write_mb,
                },
            }

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to generate performance summary: {e}")
            return {"error": str(e)}


class OP1MemoryManager:
    """Memory management optimized for OP1 LPDDR4 dual-channel"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.memory_pools: Dict[str, Any] = {}
        self.total_memory = self._get_total_memory()
        self._configure_memory_optimization()

    def _configure_memory_optimization(self) -> None:
        """Configure memory settings for OP1"""
        try:
            # Optimize for LPDDR4 dual-channel
            optimizations = {
                # Reduce swappiness for better performance with LPDDR4
                "/proc/sys/vm/swappiness": "10",
                # Optimize for dual-channel memory access
                "/proc/sys/vm/vfs_cache_pressure": "50",
                # Better memory reclaim for embedded systems
                "/proc/sys/vm/min_free_kbytes": str(
                    min(65536, self.total_memory // 32)
                ),
            }

            for path, value in optimizations.items():
                try:
                    with open(path, "w") as f:
                        f.write(value)
                    if self.logger:
                        self.logger.info(f"Set {path} = {value}")
                except PermissionError:
                    if self.logger:
                        self.logger.warning(
                            f"Cannot write to {path}, run as root for optimization"
                        )
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to optimize {path}: {e}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Memory optimization failed: {e}")

    def _get_total_memory(self) -> int:
        """Get total system memory in KB"""
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1])
        except Exception:
            return 1024 * 1024  # 1GB fallback
        return 1024 * 1024
