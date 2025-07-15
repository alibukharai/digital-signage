"""
Health monitoring service implementation with consistent error handling using Result pattern
"""

import threading
import time
from typing import Any, Dict, Optional

import psutil

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..interfaces import IHealthMonitor, ILogger


class HealthMonitorService(IHealthMonitor):
    """Concrete implementation of health monitoring service"""

    def __init__(self, check_interval: int = 30, logger: Optional[ILogger] = None):
        self.check_interval = check_interval
        self.logger = logger
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.health_data: Dict[str, Any] = {}
        self.last_check_time: Optional[float] = None

        if self.logger:
            self.logger.info("Health monitor service initialized")

    def check_system_health(self) -> Result[Dict[str, Any], Exception]:
        """Perform system health check using Result pattern for consistent error handling"""
        try:
            health_info = {
                "timestamp": time.time(),
                "cpu": self._check_cpu(),
                "memory": self._check_memory(),
                "disk": self._check_disk(),
                "network": self._check_network(),
                "processes": self._check_processes(),
                "temperature": self._check_temperature(),
                "uptime": self._get_uptime(),
                "status": "healthy",
            }

            # Determine overall health status
            health_info["status"] = self._determine_health_status(health_info)

            self.health_data = health_info
            self.last_check_time = time.time()

            if self.logger:
                self.logger.debug(f"Health check completed: {health_info['status']}")

            return Result.success(health_info)

        except Exception as e:
            error_msg = f"Health check failed: {e}"
            if self.logger:
                self.logger.error(error_msg)

            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def start_monitoring(self) -> Result[bool, Exception]:
        """Start continuous health monitoring using Result pattern for consistent error handling"""
        try:
            if self.is_monitoring:
                if self.logger:
                    self.logger.warning("Health monitoring already running")
                return Result.success(True)

            self.is_monitoring = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self.monitor_thread.start()

            if self.logger:
                self.logger.info(
                    f"Health monitoring started (interval: {self.check_interval}s)"
                )

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to start health monitoring: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def stop_monitoring(self) -> Result[bool, Exception]:
        """Stop health monitoring using Result pattern for consistent error handling"""
        try:
            if not self.is_monitoring:
                return Result.success(True)

            self.is_monitoring = False

            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)

            if self.logger:
                self.logger.info("Health monitoring stopped")

            return Result.success(True)

        except Exception as e:
            error_msg = f"Failed to stop health monitoring: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(
                SystemError(
                    ErrorCode.SYSTEM_ERROR,
                    error_msg,
                    ErrorSeverity.MEDIUM,
                )
            )

    def get_health_status(self) -> Result[str, Exception]:
        """Get current health status using Result pattern for consistent error handling"""
        try:
            if not self.health_data:
                return Result.success("unknown")

            status = self.health_data.get("status", "unknown")
            return Result.success(status)

        except Exception as e:
            error_msg = f"Failed to get health status: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(Exception(error_msg))

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                self.check_system_health()
                time.sleep(self.check_interval)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in health monitor loop: {e}")
                time.sleep(self.check_interval)

    def _check_cpu(self) -> Dict[str, Any]:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = (
                psutil.getloadavg() if hasattr(psutil, "getloadavg") else [0, 0, 0]
            )

            return {
                "usage_percent": cpu_percent,
                "core_count": cpu_count,
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2],
                },
                "status": "warning" if cpu_percent > 80 else "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent,
                "swap_used_percent": swap.percent,
                "status": "warning" if memory.percent > 85 else "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_disk(self) -> Dict[str, Any]:
        """Check disk usage"""
        try:
            disk = psutil.disk_usage("/")

            return {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_percent": round((disk.used / disk.total) * 100, 1),
                "status": "warning" if (disk.used / disk.total) > 0.9 else "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_network(self) -> Dict[str, Any]:
        """Check network interfaces"""
        try:
            interfaces = psutil.net_if_stats()
            active_interfaces = []

            for interface, stats in interfaces.items():
                if stats.isup and interface != "lo":
                    active_interfaces.append(
                        {"name": interface, "speed": stats.speed, "mtu": stats.mtu}
                    )

            return {
                "active_interfaces": active_interfaces,
                "interface_count": len(active_interfaces),
                "status": "warning" if len(active_interfaces) == 0 else "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_processes(self) -> Dict[str, Any]:
        """Check process information"""
        try:
            process_count = len(psutil.pids())

            # Check for our provisioning process
            provisioning_running = False
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if "python" in proc.info["name"].lower():
                        cmdline = (
                            " ".join(proc.info["cmdline"])
                            if proc.info["cmdline"]
                            else ""
                        )
                        if "provision" in cmdline.lower():
                            provisioning_running = True
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "total_count": process_count,
                "provisioning_running": provisioning_running,
                "status": "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_temperature(self) -> Dict[str, Any]:
        """Check system temperature"""
        try:
            temps = (
                psutil.sensors_temperatures()
                if hasattr(psutil, "sensors_temperatures")
                else {}
            )

            if temps:
                max_temp = 0
                for sensor_name, sensor_list in temps.items():
                    for sensor in sensor_list:
                        if sensor.current and sensor.current > max_temp:
                            max_temp = sensor.current

                return {
                    "max_temp_celsius": max_temp,
                    "status": "warning" if max_temp > 70 else "normal",
                }
            else:
                return {"max_temp_celsius": None, "status": "unknown"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time

            return {
                "seconds": int(uptime_seconds),
                "boot_time": boot_time,
                "status": "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _determine_health_status(self, health_info: Dict[str, Any]) -> str:
        """Determine overall health status"""
        try:
            # Check each subsystem
            subsystems = [
                "cpu",
                "memory",
                "disk",
                "network",
                "processes",
                "temperature",
            ]

            error_count = 0
            warning_count = 0

            for subsystem in subsystems:
                if subsystem in health_info:
                    status = health_info[subsystem].get("status", "unknown")
                    if status == "error":
                        error_count += 1
                    elif status == "warning":
                        warning_count += 1

            # Determine overall status
            if error_count > 2:
                return "critical"
            elif error_count > 0:
                return "degraded"
            elif warning_count > 2:
                return "degraded"
            elif warning_count > 0:
                return "warning"
            else:
                return "healthy"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to determine health status: {e}")
            return "unknown"
