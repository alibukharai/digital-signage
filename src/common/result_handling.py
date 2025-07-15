"""
Consistent error handling strategy with async support
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Generic, Optional, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")
R = TypeVar("R")


class ResultStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class Result(Generic[T, E]):
    """Result type for consistent error handling"""

    status: ResultStatus
    value: Optional[T] = None
    error: Optional[E] = None

    @classmethod
    def success(cls, value: T) -> "Result[T, E]":
        """Create successful result"""
        return cls(ResultStatus.SUCCESS, value=value)

    @classmethod
    def failure(cls, error: E) -> "Result[T, E]":
        """Create failure result"""
        return cls(ResultStatus.FAILURE, error=error)

    def is_success(self) -> bool:
        """Check if result is successful"""
        return self.status == ResultStatus.SUCCESS

    def is_failure(self) -> bool:
        """Check if result is failure"""
        return self.status == ResultStatus.FAILURE

    def map(self, func: Callable[[T], "R"]) -> "Result[R, E]":
        """Map successful value to new type"""
        if self.is_success():
            try:
                new_value = func(self.value)
                return Result.success(new_value)
            except Exception as e:
                return Result.failure(e)
        return Result.failure(self.error)

    def unwrap(self) -> T:
        """Get value or raise exception"""
        if self.is_success():
            return self.value
        raise Exception(f"Result is failure: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Get value or return default"""
        return self.value if self.is_success() else default

    async def map_async(self, func: Callable[[T], Awaitable[R]]) -> "Result[R, E]":
        """Asynchronously map successful value to new type"""
        if self.is_success():
            try:
                new_value = await func(self.value)
                return Result.success(new_value)
            except Exception as e:
                return Result.failure(e)
        return Result.failure(self.error)

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
