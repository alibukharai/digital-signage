"""
Consistent error handling strategy with async support and enhanced error context
"""

import asyncio
import time
import traceback
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")
R = TypeVar("R")


class ResultStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class ErrorContext:
    """Enhanced error context information"""

    operation: Optional[str] = None
    timestamp: Optional[float] = None
    stack_trace: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    chained_errors: list = field(default_factory=list)


@dataclass
class Result(Generic[T, E]):
    """Result type for consistent error handling with enhanced context"""

    status: ResultStatus
    value: Optional[T] = None
    error: Optional[E] = None
    context: Optional[ErrorContext] = None

    @classmethod
    def success(
        cls, value: T, context: Optional[ErrorContext] = None
    ) -> "Result[T, E]":
        """Create successful result with optional context"""
        return cls(ResultStatus.SUCCESS, value=value, context=context)

    @classmethod
    def failure(
        cls, error: E, context: Optional[ErrorContext] = None
    ) -> "Result[T, E]":
        """Create failure result with enhanced context preservation"""
        import time

        # Auto-generate context if not provided
        if context is None:
            context = ErrorContext(
                timestamp=time.time(),
                stack_trace=traceback.format_exc()
                if traceback.format_exc().strip() != "NoneType: None"
                else None,
            )

        # Enhance context with stack trace if missing
        if context.stack_trace is None:
            current_trace = traceback.format_exc()
            if current_trace.strip() != "NoneType: None":
                context.stack_trace = current_trace

        return cls(ResultStatus.FAILURE, error=error, context=context)

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        operation: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> "Result[T, Exception]":
        """Create failure result from exception with full context preservation"""
        import time

        context = ErrorContext(
            operation=operation,
            timestamp=time.time(),
            stack_trace=traceback.format_exc(),
            additional_data=additional_data or {},
        )

        # Preserve exception chain
        current_exc = exc
        while current_exc:
            context.chained_errors.append(
                {
                    "type": type(current_exc).__name__,
                    "message": str(current_exc),
                    "args": current_exc.args,
                }
            )
            current_exc = getattr(current_exc, "__cause__", None) or getattr(
                current_exc, "__context__", None
            )

        return cls(ResultStatus.FAILURE, error=exc, context=context)

    def is_success(self) -> bool:
        """Check if result is successful"""
        return self.status == ResultStatus.SUCCESS

    def is_failure(self) -> bool:
        """Check if result is failure"""
        return self.status == ResultStatus.FAILURE

    def map(self, func: Callable[[T], "R"]) -> "Result[R, E]":
        """Map successful value to new type with enhanced error context"""
        if self.is_success():
            try:
                new_value = func(self.value)
                return Result.success(new_value, self.context)
            except Exception as e:
                # Preserve error chain and add context
                error_context = ErrorContext(
                    operation="map_operation",
                    timestamp=time.time(),
                    stack_trace=traceback.format_exc(),
                    additional_data={"original_value_type": type(self.value).__name__},
                )

                # Chain with previous context if available
                if self.context:
                    error_context.chained_errors.append(
                        {
                            "previous_operation": self.context.operation,
                            "previous_timestamp": self.context.timestamp,
                        }
                    )

                return Result.failure(e, error_context)
        return Result.failure(self.error, self.context)

    def unwrap(self) -> T:
        """Get value or raise exception with full context"""
        if self.is_success():
            return self.value

        # Create enhanced exception with context
        if self.context and self.context.stack_trace:
            error_msg = f"Result is failure: {self.error}"
            if self.context.operation:
                error_msg += f" (operation: {self.context.operation})"
            if self.context.chained_errors:
                error_msg += f" (chained errors: {len(self.context.chained_errors)})"

            # Create new exception with context
            enhanced_error = Exception(error_msg)
            enhanced_error.__cause__ = (
                self.error
                if isinstance(self.error, Exception)
                else Exception(str(self.error))
            )
            raise enhanced_error
        else:
            raise Exception(f"Result is failure: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Get value or return default"""
        return self.value if self.is_success() else default

    def unwrap_or_else(self, func: Callable[[E], T]) -> T:
        """Get value or call function with error to get default"""
        if self.is_success():
            return self.value
        return func(self.error)

    async def map_async(self, func: Callable[[T], Awaitable[R]]) -> "Result[R, E]":
        """Asynchronously map successful value to new type with context preservation"""
        if self.is_success():
            try:
                new_value = await func(self.value)
                return Result.success(new_value, self.context)
            except Exception as e:
                error_context = ErrorContext(
                    operation="async_map_operation",
                    timestamp=time.time(),
                    stack_trace=traceback.format_exc(),
                    additional_data={"original_value_type": type(self.value).__name__},
                )

                if self.context:
                    error_context.chained_errors.append(
                        {
                            "previous_operation": self.context.operation,
                            "previous_timestamp": self.context.timestamp,
                        }
                    )

                return Result.failure(e, error_context)
        return Result.failure(self.error, self.context)

    def and_then(self, func: Callable[[T], "Result[R, E]"]) -> "Result[R, E]":
        """Chain result operations (flatMap/bind)"""
        if self.is_success():
            return func(self.value)
        return Result.failure(self.error)

    async def and_then_async(
        self, func: Callable[[T], Awaitable["Result[R, E]"]]
    ) -> "Result[R, E]":
        """Asynchronously chain result operations"""
        if self.is_success():
            return await func(self.value)
        return Result.failure(self.error)

    def get_error_summary(self) -> Optional[str]:
        """Get a comprehensive error summary including context"""
        if self.is_success():
            return None

        summary = f"Error: {self.error}"

        if self.context:
            if self.context.operation:
                summary += f" (Operation: {self.context.operation})"

            if self.context.timestamp:
                import datetime

                dt = datetime.datetime.fromtimestamp(self.context.timestamp)
                summary += f" (Time: {dt.isoformat()})"

            if self.context.chained_errors:
                summary += f" (Chained errors: {len(self.context.chained_errors)})"
                for i, chained in enumerate(
                    self.context.chained_errors[:3]
                ):  # Show first 3
                    summary += f"\n  {i+1}. {chained.get('type', 'Unknown')}: {chained.get('message', 'No message')}"

        return summary

    def log_error(self, logger, prefix: str = "Operation failed") -> None:
        """Log error with full context to provided logger"""
        if self.is_failure() and logger:
            error_summary = self.get_error_summary()
            logger.error(f"{prefix}: {error_summary}")

            if self.context and self.context.stack_trace:
                logger.debug(f"Full stack trace: {self.context.stack_trace}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization"""
        result_dict = {"status": self.status.value, "success": self.is_success()}

        if self.is_success():
            # Only include serializable values
            try:
                if isinstance(
                    self.value, (str, int, float, bool, list, dict, type(None))
                ):
                    result_dict["value"] = self.value
                else:
                    result_dict["value"] = str(self.value)
            except:
                result_dict["value"] = "<non-serializable>"
        else:
            result_dict["error"] = str(self.error)

            if self.context:
                context_dict = {}
                if self.context.operation:
                    context_dict["operation"] = self.context.operation
                if self.context.timestamp:
                    context_dict["timestamp"] = self.context.timestamp
                if self.context.additional_data:
                    context_dict["additional_data"] = self.context.additional_data
                if self.context.chained_errors:
                    context_dict["chained_error_count"] = len(
                        self.context.chained_errors
                    )

                if context_dict:
                    result_dict["context"] = context_dict

        return result_dict


class ResultBuilder:
    """Builder for creating results with context"""

    def __init__(self, operation: Optional[str] = None):
        self.operation = operation
        self.additional_data: Dict[str, Any] = {}

    def add_context(self, key: str, value: Any) -> "ResultBuilder":
        """Add additional context data"""
        self.additional_data[key] = value
        return self

    def success(self, value: T) -> Result[T, Any]:
        """Build success result"""
        context = None
        if self.operation or self.additional_data:
            context = ErrorContext(
                operation=self.operation,
                timestamp=time.time(),
                additional_data=self.additional_data,
            )
        return Result.success(value, context)

    def failure(self, error: Any) -> Result[Any, Any]:
        """Build failure result"""
        context = ErrorContext(
            operation=self.operation,
            timestamp=time.time(),
            stack_trace=traceback.format_exc(),
            additional_data=self.additional_data,
        )
        return Result.failure(error, context)


@contextmanager
def result_operation(operation_name: str, logger=None):
    """Context manager for operations that return Results"""
    start_time = time.time()
    try:
        if logger:
            logger.debug(f"Starting operation: {operation_name}")
        yield ResultBuilder(operation_name)
    except Exception as e:
        duration = time.time() - start_time
        if logger:
            logger.error(
                f"Operation {operation_name} failed after {duration:.2f}s: {e}"
            )
        raise
    finally:
        duration = time.time() - start_time
        if logger:
            logger.debug(f"Operation {operation_name} completed in {duration:.2f}s")


class IResultHandler(ABC, Generic[T, E]):
    """Interface for handling results"""

    @abstractmethod
    def handle_success(self, value: T) -> None:
        """Handle successful result"""
        pass

    @abstractmethod
    def handle_failure(self, error: E) -> None:
        """Handle failed result"""
        pass


class LoggingResultHandler(IResultHandler[T, Exception]):
    """Result handler that logs outcomes"""

    def __init__(self, logger, operation_name: str):
        self.logger = logger
        self.operation_name = operation_name

    def handle_success(self, value: T) -> None:
        if self.logger:
            self.logger.info(f"{self.operation_name} completed successfully")

    def handle_failure(self, error: Exception) -> None:
        if self.logger:
            self.logger.error(f"{self.operation_name} failed: {error}")


# Example of improved service with consistent error handling
class ImprovedNetworkService:
    """Network service with consistent error handling using Result type"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def scan_networks(self) -> Result[list, Exception]:
        """Scan networks with Result return type"""
        try:
            # Actual network scanning logic
            networks = self._perform_network_scan()

            if self.logger:
                self.logger.info(f"Network scan found {len(networks)} networks")

            return Result.success(networks)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Network scan failed: {e}")
            return Result.failure(e)

    def connect_to_network(self, ssid: str, password: str) -> Result[bool, Exception]:
        """Connect to network with Result return type"""
        try:
            # Validate inputs
            if not ssid or not password:
                raise ValueError("SSID and password are required")

            # Perform connection
            success = self._perform_connection(ssid, password)

            if success:
                if self.logger:
                    self.logger.info(f"Successfully connected to {ssid}")
                return Result.success(True)
            else:
                error = Exception(f"Failed to connect to {ssid}")
                if self.logger:
                    self.logger.error(str(error))
                return Result.failure(error)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Connection attempt failed: {e}")
            return Result.failure(e)

    def _perform_network_scan(self) -> list:
        """Network scan implementation"""
        # Actual implementation would use system commands
        return []

    def _perform_connection(self, ssid: str, password: str) -> bool:
        """Network connection implementation"""
        # Actual implementation would use system commands
        return True


# Usage example with consistent error handling
class NetworkProvisioningUseCaseImproved:
    """Improved use case with consistent error handling"""

    def __init__(self, network_service: ImprovedNetworkService, logger):
        self.network_service = network_service
        self.logger = logger

    def provision_network(self, ssid: str, password: str) -> Result[bool, str]:
        """Provision network with proper error handling"""

        # Scan networks first
        scan_result = self.network_service.scan_networks()
        if scan_result.is_failure():
            return Result.failure(f"Network scan failed: {scan_result.error}")

        available_networks = scan_result.value

        # Check if target network is available
        target_network = next((n for n in available_networks if n.ssid == ssid), None)
        if not target_network:
            return Result.failure(f"Network '{ssid}' not found in scan results")

        # Attempt connection
        connect_result = self.network_service.connect_to_network(ssid, password)
        if connect_result.is_failure():
            return Result.failure(f"Connection failed: {connect_result.error}")

        return Result.success(True)
