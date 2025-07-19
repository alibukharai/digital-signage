"""
Health monitoring service implementation with consistent error handling using Result pattern
Enhanced with proper threading coordination and metric accuracy
"""

import asyncio
import threading
import time
import weakref
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

import psutil

from ..common.result_handling import Result
from ..domain.errors import ErrorCode, ErrorSeverity, SystemError
from ..interfaces import IHealthMonitor, ILogger


class HealthMonitorService(IHealthMonitor):
    """Concrete implementation of health monitoring service with enhanced threading coordination"""

    def __init__(self, check_interval: int = 30, logger: Optional[ILogger] = None):
        self.check_interval = check_interval
        self.logger = logger
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.health_data: Dict[str, Any] = {}
        self.last_check_time: Optional[float] = None

        # Enhanced threading coordination
        self._shutdown_event = threading.Event()
        self._state_lock = threading.RLock()  # Reentrant lock for state management
        self._metric_collection_lock = threading.Lock()  # Separate lock for metrics
        self._lifecycle_callbacks: List[Callable] = []
        self._error_handlers: List[Callable[[Exception], None]] = []

        # Metric accuracy improvements
        self._metric_history: Dict[str, List[Any]] = {}
        self._metric_validation_enabled = True
        self._baseline_metrics: Optional[Dict[str, Any]] = None

        # Resource management
        self._active_operations: weakref.WeakSet = weakref.WeakSet()

        if self.logger:
            self.logger.info(
                "Health monitor service initialized with enhanced coordination"
            )

    async def start_monitoring_async(self) -> Result[None, Exception]:
        """Start async monitoring (for use in async contexts)"""
        try:
            with self._state_lock:
                if self.is_monitoring:
                    return Result.success(None)

                # Clear shutdown event
                self._shutdown_event.clear()

                # Initialize baseline metrics
                self._establish_baseline_metrics()

                self.is_monitoring = True

                # Start async monitoring task instead of thread
                self._monitor_task = asyncio.create_task(self._monitor_loop_async())

                if self.logger:
                    self.logger.info("Async health monitoring started")

                return Result.success(None)

        except Exception as e:
            error_msg = f"Failed to start async health monitoring: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(Exception(error_msg))

    async def stop_monitoring_async(self) -> Result[None, Exception]:
        """Stop async monitoring"""
        try:
            with self._state_lock:
                if not self.is_monitoring:
                    return Result.success(None)

                self.is_monitoring = False
                self._shutdown_event.set()

                # Cancel async task if it exists
                if hasattr(self, '_monitor_task') and self._monitor_task:
                    self._monitor_task.cancel()
                    try:
                        await self._monitor_task
                    except asyncio.CancelledError:
                        pass

                if self.logger:
                    self.logger.info("Async health monitoring stopped")

                return Result.success(None)

        except Exception as e:
            error_msg = f"Failed to stop async health monitoring: {e}"
            if self.logger:
                self.logger.error(error_msg)
            return Result.failure(Exception(error_msg))

    def check_system_health(self) -> Result[Dict[str, Any], Exception]:
        """Perform system health check with enhanced accuracy and coordination"""
        with self._operation_context("system_health_check"):
            try:
                with self._metric_collection_lock:
                    health_info = {
                        "timestamp": time.time(),
                        "cpu": self._check_cpu_enhanced(),
                        "memory": self._check_memory_enhanced(),
                        "disk": self._check_disk_enhanced(),
                        "network": self._check_network_enhanced(),
                        "processes": self._check_processes_enhanced(),
                        "temperature": self._check_temperature_enhanced(),
                        "uptime": self._get_uptime_enhanced(),
                        "status": "healthy",
                        "validation_passed": True,
                        "active_operations": len(self._active_operations),
                    }

                    # Validate metrics against historical data
                    validation_results = {}
                    for key, value in health_info.items():
                        if key in ["cpu", "memory", "disk"] and isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                metric_name = f"{key}_{sub_key}"
                                if metric_name in self._metric_history:
                                    is_valid = self._validate_metric(
                                        metric_name,
                                        sub_value,
                                        self._metric_history[metric_name],
                                    )
                                    validation_results[metric_name] = is_valid
                                    if not is_valid:
                                        health_info["validation_passed"] = False

                    # Store metrics in history for future validation
                    self._update_metric_history(health_info)

                    # Determine overall health status with enhanced logic
                    health_info["status"] = self._determine_health_status_enhanced(
                        health_info
                    )
                    health_info["validation_results"] = validation_results

                    # Thread-safe update of shared state
                    with self._state_lock:
                        self.health_data = health_info
                        self.last_check_time = time.time()

                    if self.logger:
                        self.logger.debug(
                            f"Health check completed: {health_info['status']} (validation: {health_info['validation_passed']})"
                        )

                    return Result.success(health_info)

            except Exception as e:
                error_msg = f"Health check failed: {e}"
                if self.logger:
                    self.logger.error(error_msg)

                # Enhanced error context preservation
                import traceback

                full_traceback = traceback.format_exc()
                if self.logger:
                    self.logger.error(f"Health check full traceback: {full_traceback}")

                return Result.failure(
                    SystemError(
                        ErrorCode.SYSTEM_ERROR,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                        context={
                            "operation": "health_check",
                            "traceback": full_traceback,
                        },
                    )
                )

    def start_monitoring(self) -> Result[bool, Exception]:
        """Start continuous health monitoring with enhanced threading coordination"""
        with self._state_lock:
            try:
                if self.is_monitoring:
                    if self.logger:
                        self.logger.warning("Health monitoring already running")
                    return Result.success(True)

                # Clear shutdown event
                self._shutdown_event.clear()

                # Initialize baseline metrics
                self._establish_baseline_metrics()

                self.is_monitoring = True
                self.monitor_thread = threading.Thread(
                    target=self._monitor_loop_enhanced,
                    daemon=False,  # Not daemon for proper shutdown
                    name="HealthMonitor",
                )
                self.monitor_thread.start()

                # Notify lifecycle callbacks
                for callback in self._lifecycle_callbacks:
                    try:
                        callback("monitoring_started")
                    except Exception as cb_error:
                        if self.logger:
                            self.logger.error(f"Lifecycle callback failed: {cb_error}")

                if self.logger:
                    self.logger.info(
                        f"Health monitoring started with enhanced coordination (interval: {self.check_interval}s)"
                    )

                return Result.success(True)

            except Exception as e:
                error_msg = f"Failed to start health monitoring: {e}"
                if self.logger:
                    self.logger.error(error_msg)

                # Reset state on failure
                self.is_monitoring = False
                self._shutdown_event.set()

                return Result.failure(
                    SystemError(
                        ErrorCode.SYSTEM_ERROR,
                        error_msg,
                        ErrorSeverity.MEDIUM,
                        context={"operation": "start_monitoring"},
                    )
                )

    def stop_monitoring(self) -> Result[bool, Exception]:
        """Stop health monitoring with proper resource cleanup and coordination"""
        with self._state_lock:
            try:
                if not self.is_monitoring:
                    return Result.success(True)

                # Signal shutdown
                self._shutdown_event.set()
                self.is_monitoring = False

                # Wait for thread to finish with timeout
                if self.monitor_thread and self.monitor_thread.is_alive():
                    self.monitor_thread.join(timeout=10)  # Increased timeout

                    if self.monitor_thread.is_alive():
                        if self.logger:
                            self.logger.warning(
                                "Health monitor thread did not shutdown gracefully"
                            )
                        # Force cleanup
                        self.monitor_thread = None

                # Notify lifecycle callbacks
                for callback in self._lifecycle_callbacks:
                    try:
                        callback("monitoring_stopped")
                    except Exception as cb_error:
                        if self.logger:
                            self.logger.error(f"Lifecycle callback failed: {cb_error}")

                # Clean up resources
                self._cleanup_resources()

                if self.logger:
                    self.logger.info("Health monitoring stopped with proper cleanup")

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
                        context={"operation": "stop_monitoring"},
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
        """Main monitoring loop - DEPRECATED: Use async version instead"""
        if self.logger:
            self.logger.warning("Using deprecated synchronous monitor loop. Consider using async version.")
        
        while self.is_monitoring:
            try:
                self.check_system_health()
                # Use threading event instead of blocking sleep
                if self._shutdown_event.wait(self.check_interval):
                    break
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in health monitor loop: {e}")
                if self._shutdown_event.wait(self.check_interval):
                    break

    async def _monitor_loop_async(self):
        """Async monitoring loop for use in async contexts"""
        if self.logger:
            self.logger.info("Starting async health monitoring loop")
        
        while self.is_monitoring and not self._shutdown_event.is_set():
            try:
                self.check_system_health()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in async health monitor loop: {e}")
                await asyncio.sleep(self.check_interval)

    def _monitor_loop_enhanced(self):
        """Enhanced monitoring loop with proper coordination and error handling"""
        try:
            if self.logger:
                self.logger.info("Health monitoring loop started")

            while not self._shutdown_event.is_set():
                try:
                    # Check if we should continue monitoring
                    if not self.is_monitoring:
                        break

                    # Perform health check with timeout
                    result = self.check_system_health()

                    if result.is_failure() and self.logger:
                        self.logger.error(
                            f"Health check failed in monitoring loop: {result.error}"
                        )

                    # Wait for next check with early exit on shutdown
                    if self._shutdown_event.wait(timeout=self.check_interval):
                        break  # Shutdown requested

                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error in enhanced health monitor loop: {e}")

                    # Wait before retrying, but allow early exit
                    if self._shutdown_event.wait(timeout=min(self.check_interval, 30)):
                        break

        except Exception as e:
            if self.logger:
                self.logger.error(f"Fatal error in health monitoring loop: {e}")
        finally:
            if self.logger:
                self.logger.info("Health monitoring loop ended")

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

    def register_lifecycle_callback(self, callback: Callable) -> None:
        """Register callback for lifecycle events"""
        with self._state_lock:
            self._lifecycle_callbacks.append(callback)

    def register_error_handler(self, handler: Callable[[Exception], None]) -> None:
        """Register error handler for metric collection issues"""
        with self._state_lock:
            self._error_handlers.append(handler)

    @contextmanager
    def _operation_context(self, operation_name: str):
        """Context manager for tracking active operations"""
        operation_id = f"{operation_name}_{time.time()}"
        self._active_operations.add(operation_id)
        try:
            if self.logger:
                self.logger.debug(f"Starting operation: {operation_name}")
            yield operation_id
        except Exception as e:
            if self.logger:
                self.logger.error(f"Operation {operation_name} failed: {e}")
            # Notify error handlers
            for handler in self._error_handlers:
                try:
                    handler(e)
                except Exception as handler_error:
                    if self.logger:
                        self.logger.error(f"Error handler failed: {handler_error}")
            raise
        finally:
            try:
                self._active_operations.discard(operation_id)
            except:
                pass  # WeakSet may already be cleaned up
            if self.logger:
                self.logger.debug(f"Completed operation: {operation_name}")

    def _validate_metric(
        self, metric_name: str, current_value: Any, historical_values: List[Any]
    ) -> bool:
        """Validate metric for accuracy under edge conditions"""
        if not self._metric_validation_enabled or not historical_values:
            return True

        try:
            # Basic validation - check for impossible values
            if metric_name.endswith("_percent") and isinstance(
                current_value, (int, float)
            ):
                if current_value < 0 or current_value > 100:
                    if self.logger:
                        self.logger.warning(
                            f"Invalid percentage value for {metric_name}: {current_value}"
                        )
                    return False

            # Statistical validation - detect outliers
            if len(historical_values) >= 3 and isinstance(current_value, (int, float)):
                import statistics

                try:
                    mean = statistics.mean(historical_values[-10:])  # Last 10 values
                    stdev = statistics.stdev(historical_values[-10:])
                    # Value is outlier if it's more than 3 standard deviations from mean
                    if abs(current_value - mean) > 3 * stdev:
                        if self.logger:
                            self.logger.warning(
                                f"Outlier detected for {metric_name}: {current_value} (mean: {mean:.2f}, stdev: {stdev:.2f})"
                            )
                        return False
                except statistics.StatisticsError:
                    # Not enough data for validation
                    pass

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Metric validation failed for {metric_name}: {e}")
            return True  # Default to accepting the value if validation fails

    def _establish_baseline_metrics(self) -> None:
        """Establish baseline metrics for comparison"""
        try:
            baseline_result = self.check_system_health()
            if baseline_result.is_success():
                self._baseline_metrics = baseline_result.value
                if self.logger:
                    self.logger.info("Baseline metrics established")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to establish baseline metrics: {e}")

    def _update_metric_history(self, health_info: Dict[str, Any]) -> None:
        """Update metric history for validation"""
        try:
            max_history_length = 50  # Keep last 50 measurements

            for category in ["cpu", "memory", "disk"]:
                if category in health_info and isinstance(health_info[category], dict):
                    for key, value in health_info[category].items():
                        if isinstance(value, (int, float)):
                            metric_name = f"{category}_{key}"
                            if metric_name not in self._metric_history:
                                self._metric_history[metric_name] = []

                            self._metric_history[metric_name].append(value)

                            # Trim history to prevent memory growth
                            if (
                                len(self._metric_history[metric_name])
                                > max_history_length
                            ):
                                self._metric_history[
                                    metric_name
                                ] = self._metric_history[metric_name][
                                    -max_history_length:
                                ]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to update metric history: {e}")

    def _cleanup_resources(self) -> None:
        """Clean up resources during shutdown"""
        try:
            # Clear metric history to free memory
            self._metric_history.clear()

            # Clear callbacks to prevent memory leaks
            self._lifecycle_callbacks.clear()
            self._error_handlers.clear()

            # Clear baseline metrics
            self._baseline_metrics = None

            if self.logger:
                self.logger.debug("Resources cleaned up successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during resource cleanup: {e}")

    def __enter__(self):
        """Context manager entry"""
        start_result = self.start_monitoring()
        if start_result.is_failure():
            raise Exception(f"Failed to start health monitoring: {start_result.error}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper cleanup"""
        stop_result = self.stop_monitoring()
        if stop_result.is_failure() and self.logger:
            self.logger.error(
                f"Failed to stop health monitoring cleanly: {stop_result.error}"
            )

    # Enhanced metric collection methods
    def _check_cpu_enhanced(self) -> Dict[str, Any]:
        """Enhanced CPU check with better accuracy"""
        try:
            # Multiple samples for more accurate reading
            cpu_samples = []
            for _ in range(3):
                cpu_samples.append(psutil.cpu_percent(interval=0.1))

            cpu_percent = sum(cpu_samples) / len(cpu_samples)
            cpu_count = psutil.cpu_count()
            logical_count = psutil.cpu_count(logical=True)

            # Get load average if available
            try:
                load_avg = (
                    psutil.getloadavg() if hasattr(psutil, "getloadavg") else [0, 0, 0]
                )
            except (AttributeError, OSError):
                load_avg = [0, 0, 0]

            # Get per-CPU usage
            per_cpu = psutil.cpu_percent(percpu=True, interval=0.1)

            return {
                "usage_percent": round(cpu_percent, 2),
                "core_count": cpu_count,
                "logical_count": logical_count,
                "per_cpu_usage": [round(usage, 2) for usage in per_cpu],
                "load_average": {
                    "1min": round(load_avg[0], 2),
                    "5min": round(load_avg[1], 2),
                    "15min": round(load_avg[2], 2),
                },
                "status": "critical"
                if cpu_percent > 95
                else "warning"
                if cpu_percent > 80
                else "normal",
                "samples_taken": len(cpu_samples),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "fallback": True}

    def _check_memory_enhanced(self) -> Dict[str, Any]:
        """Enhanced memory check with swap details"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Calculate additional metrics
            available_percent = (memory.available / memory.total) * 100

            return {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "free_gb": round(memory.free / (1024**3), 2),
                "used_percent": round(memory.percent, 2),
                "available_percent": round(available_percent, 2),
                "cached_gb": round(getattr(memory, "cached", 0) / (1024**3), 2),
                "buffers_gb": round(getattr(memory, "buffers", 0) / (1024**3), 2),
                "swap": {
                    "total_gb": round(swap.total / (1024**3), 2),
                    "used_gb": round(swap.used / (1024**3), 2),
                    "used_percent": round(swap.percent, 2),
                },
                "status": "critical"
                if memory.percent > 95
                else "warning"
                if memory.percent > 85
                else "normal",
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "fallback": True}

    def _determine_health_status_enhanced(self, health_info: Dict[str, Any]) -> str:
        """Enhanced health status determination with better logic"""
        try:
            statuses = []

            # Collect all component statuses
            for component in ["cpu", "memory", "disk", "network", "temperature"]:
                if component in health_info and isinstance(
                    health_info[component], dict
                ):
                    status = health_info[component].get("status", "unknown")
                    statuses.append(status)

            # Check validation status
            if not health_info.get("validation_passed", True):
                statuses.append("warning")  # Validation failures are concerning

            # Determine overall status
            if "critical" in statuses:
                return "critical"
            elif "error" in statuses:
                return "error"
            elif "warning" in statuses:
                return "warning"
            elif "unknown" in statuses:
                return "degraded"
            else:
                return "healthy"

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to determine health status: {e}")
            return "unknown"
