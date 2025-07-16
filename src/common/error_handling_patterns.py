"""
Standardized error handling patterns and utilities for consistent error management
"""

import asyncio
import functools
import inspect
import time
import traceback
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Union

from .result_handling import ErrorContext, Result, ResultBuilder

T = TypeVar("T")
F = TypeVar("F", bound=Callable)


class ErrorHandlingMixin:
    """Mixin to provide standardized error handling methods to any class"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._error_context: Dict[str, Any] = {}
        self._operation_history: list = []

    def _get_logger(self):
        """Get logger if available"""
        return getattr(self, "logger", None)

    def _add_operation_context(self, operation: str, **context) -> None:
        """Add context for current operation"""
        self._error_context.update(context)
        self._operation_history.append(
            {
                "operation": operation,
                "timestamp": time.time(),
                "context": context.copy(),
            }
        )

        # Keep only last 10 operations to prevent memory growth
        if len(self._operation_history) > 10:
            self._operation_history = self._operation_history[-10:]

    def _create_error_result(
        self, error: Exception, operation: str, **additional_context
    ) -> Result[Any, Exception]:
        """Create standardized error result with full context"""
        context = ErrorContext(
            operation=operation,
            timestamp=time.time(),
            stack_trace=traceback.format_exc(),
            additional_data={
                **self._error_context,
                **additional_context,
                "operation_history": self._operation_history[-3:],  # Last 3 operations
            },
        )

        logger = self._get_logger()
        if logger:
            logger.error(f"Operation {operation} failed: {error}")
            if additional_context:
                logger.debug(f"Additional context: {additional_context}")

        return Result.failure(error, context)

    def _create_success_result(
        self, value: T, operation: str, **additional_context
    ) -> Result[T, Exception]:
        """Create standardized success result with context"""
        context = (
            ErrorContext(
                operation=operation,
                timestamp=time.time(),
                additional_data={**self._error_context, **additional_context},
            )
            if additional_context
            else None
        )

        logger = self._get_logger()
        if logger:
            logger.debug(f"Operation {operation} completed successfully")

        return Result.success(value, context)


def with_error_handling(operation_name: Optional[str] = None):
    """Decorator to add standardized error handling to methods"""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine operation name
            op_name = operation_name or f"{func.__module__}.{func.__qualname__}"

            # Get instance if this is a method
            instance = args[0] if args and hasattr(args[0], "__dict__") else None
            logger = getattr(instance, "logger", None) if instance else None

            try:
                if logger:
                    logger.debug(f"Starting operation: {op_name}")

                result = func(*args, **kwargs)

                # If function returns a Result, pass it through
                if isinstance(result, Result):
                    return result

                # Wrap successful result
                if logger:
                    logger.debug(f"Operation {op_name} completed successfully")

                return result

            except Exception as e:
                if logger:
                    logger.error(f"Operation {op_name} failed: {e}")
                    logger.debug(f"Full traceback: {traceback.format_exc()}")

                # If this is a method on a class with error handling, use that
                if instance and hasattr(instance, "_create_error_result"):
                    return instance._create_error_result(e, op_name)

                # Otherwise create a basic error result
                context = ErrorContext(
                    operation=op_name,
                    timestamp=time.time(),
                    stack_trace=traceback.format_exc(),
                )
                return Result.failure(e, context)

        return wrapper

    return decorator


def with_async_error_handling(operation_name: Optional[str] = None):
    """Decorator to add standardized error handling to async methods"""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Determine operation name
            op_name = operation_name or f"{func.__module__}.{func.__qualname__}"

            # Get instance if this is a method
            instance = args[0] if args and hasattr(args[0], "__dict__") else None
            logger = getattr(instance, "logger", None) if instance else None

            try:
                if logger:
                    logger.debug(f"Starting async operation: {op_name}")

                result = await func(*args, **kwargs)

                # If function returns a Result, pass it through
                if isinstance(result, Result):
                    return result

                # Wrap successful result
                if logger:
                    logger.debug(f"Async operation {op_name} completed successfully")

                return result

            except Exception as e:
                if logger:
                    logger.error(f"Async operation {op_name} failed: {e}")
                    logger.debug(f"Full traceback: {traceback.format_exc()}")

                # If this is a method on a class with error handling, use that
                if instance and hasattr(instance, "_create_error_result"):
                    return instance._create_error_result(e, op_name)

                # Otherwise create a basic error result
                context = ErrorContext(
                    operation=op_name,
                    timestamp=time.time(),
                    stack_trace=traceback.format_exc(),
                )
                return Result.failure(e, context)

        return wrapper

    return decorator


@contextmanager
def operation_context(name: str, logger=None, **context):
    """Context manager for operations with automatic error handling"""
    start_time = time.time()
    try:
        if logger:
            logger.debug(f"Starting operation: {name}")
            if context:
                logger.debug(f"Operation context: {context}")
        yield
    except Exception as e:
        duration = time.time() - start_time
        if logger:
            logger.error(f"Operation {name} failed after {duration:.2f}s: {e}")
        raise
    finally:
        duration = time.time() - start_time
        if logger:
            logger.debug(f"Operation {name} completed in {duration:.2f}s")


@asynccontextmanager
async def async_operation_context(name: str, logger=None, **context):
    """Async context manager for operations with automatic error handling"""
    start_time = time.time()
    try:
        if logger:
            logger.debug(f"Starting async operation: {name}")
            if context:
                logger.debug(f"Operation context: {context}")
        yield
    except Exception as e:
        duration = time.time() - start_time
        if logger:
            logger.error(f"Async operation {name} failed after {duration:.2f}s: {e}")
        raise
    finally:
        duration = time.time() - start_time
        if logger:
            logger.debug(f"Async operation {name} completed in {duration:.2f}s")


class ResourceManager:
    """Context manager for proper resource cleanup"""

    def __init__(self, logger=None):
        self.logger = logger
        self._resources: list = []
        self._cleanup_callbacks: list = []

    def add_resource(self, resource, cleanup_method: str = "close"):
        """Add a resource to be cleaned up"""
        self._resources.append((resource, cleanup_method))
        return resource

    def add_cleanup_callback(self, callback: Callable):
        """Add a cleanup callback function"""
        self._cleanup_callbacks.append(callback)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up all resources"""
        errors = []

        # Run cleanup callbacks first
        for callback in reversed(self._cleanup_callbacks):
            try:
                callback()
            except Exception as e:
                errors.append(f"Cleanup callback failed: {e}")
                if self.logger:
                    self.logger.error(f"Cleanup callback failed: {e}")

        # Clean up resources
        for resource, cleanup_method in reversed(self._resources):
            try:
                if hasattr(resource, cleanup_method):
                    cleanup_func = getattr(resource, cleanup_method)
                    if callable(cleanup_func):
                        cleanup_func()
                elif hasattr(resource, "__exit__"):
                    resource.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                errors.append(f"Resource cleanup failed: {e}")
                if self.logger:
                    self.logger.error(f"Resource cleanup failed for {resource}: {e}")

        # Log summary if there were errors
        if errors and self.logger:
            self.logger.warning(f"Resource cleanup completed with {len(errors)} errors")
        elif self.logger:
            self.logger.debug("All resources cleaned up successfully")


async def safe_gather(*awaitables, return_exceptions: bool = True, logger=None):
    """Safe version of asyncio.gather with proper error handling"""
    try:
        if logger:
            logger.debug(f"Gathering {len(awaitables)} async operations")

        results = await asyncio.gather(*awaitables, return_exceptions=return_exceptions)

        # Count successful vs failed operations
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = len(results) - successes

        if logger:
            logger.info(
                f"Async gather completed: {successes} succeeded, {failures} failed"
            )

        return results

    except Exception as e:
        if logger:
            logger.error(f"Async gather failed completely: {e}")
        raise


def retry_with_backoff(
    max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
):
    """Decorator for retrying operations with exponential backoff"""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            instance = args[0] if args and hasattr(args[0], "__dict__") else None
            logger = getattr(instance, "logger", None) if instance else None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        if logger:
                            logger.error(
                                f"Operation failed after {max_retries} retries: {e}"
                            )
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    if logger:
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s"
                        )

                    await asyncio.sleep(delay)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            instance = args[0] if args and hasattr(args[0], "__dict__") else None
            logger = getattr(instance, "logger", None) if instance else None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        if logger:
                            logger.error(
                                f"Operation failed after {max_retries} retries: {e}"
                            )
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    if logger:
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s"
                        )

                    time.sleep(delay)

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
