"""
Concurrency and threading coordination utilities to address mixed async/threading patterns
"""

import asyncio
import threading
import time
import weakref
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, TypeVar, Union

T = TypeVar("T")


class CoordinationMode(Enum):
    """Coordination modes for mixed async/sync operations"""

    ASYNC_ONLY = "async_only"
    SYNC_ONLY = "sync_only"
    MIXED = "mixed"
    AUTO_DETECT = "auto_detect"


@dataclass
class ThreadOperationInfo:
    """Information about a thread operation"""

    thread_id: int
    operation_name: str
    start_time: float
    is_daemon: bool
    coordination_mode: CoordinationMode


class ThreadCoordinator:
    """Coordinates between threading and async operations"""

    def __init__(self, logger=None):
        self.logger = logger
        self._active_threads: Dict[int, ThreadOperationInfo] = {}
        self._async_tasks: weakref.WeakSet = weakref.WeakSet()
        self._coordination_lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._coordination_mode = CoordinationMode.AUTO_DETECT

        # Track async loop if available
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread_id: Optional[int] = None

    def set_coordination_mode(self, mode: CoordinationMode) -> None:
        """Set the coordination mode for operations"""
        with self._coordination_lock:
            self._coordination_mode = mode
            if self.logger:
                self.logger.info(f"Thread coordination mode set to: {mode.value}")

    def register_async_loop(
        self, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        """Register the main async event loop"""
        with self._coordination_lock:
            self._loop = loop or asyncio.get_event_loop()
            self._loop_thread_id = threading.get_ident()
            if self.logger:
                self.logger.info(
                    f"Async event loop registered on thread {self._loop_thread_id}"
                )

    @contextmanager
    def thread_operation(self, operation_name: str, daemon: bool = True):
        """Context manager for thread operations with coordination"""
        thread_id = threading.get_ident()

        with self._coordination_lock:
            operation_info = ThreadOperationInfo(
                thread_id=thread_id,
                operation_name=operation_name,
                start_time=time.time(),
                is_daemon=daemon,
                coordination_mode=self._coordination_mode,
            )
            self._active_threads[thread_id] = operation_info

        try:
            if self.logger:
                self.logger.debug(
                    f"Started thread operation: {operation_name} (thread {thread_id})"
                )
            yield operation_info
        finally:
            with self._coordination_lock:
                if thread_id in self._active_threads:
                    duration = time.time() - operation_info.start_time
                    del self._active_threads[thread_id]
                    if self.logger:
                        self.logger.debug(
                            f"Completed thread operation: {operation_name} in {duration:.2f}s"
                        )

    async def run_in_thread(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run a sync function in a thread from async context"""
        if not self._loop:
            self.register_async_loop()

        # Use thread pool for CPU-bound operations
        loop = self._loop or asyncio.get_event_loop()

        def wrapped_func():
            with self.thread_operation(f"async_to_sync_{func.__name__}"):
                return func(*args, **kwargs)

        return await loop.run_in_executor(None, wrapped_func)

    def run_async_from_sync(self, coro: Awaitable[T]) -> T:
        """Run an async coroutine from sync context"""
        if self._loop and self._loop_thread_id == threading.get_ident():
            # We're already in the event loop thread
            raise RuntimeError("Cannot run async from within the event loop thread")

        # Check if there's a running loop in another thread
        if self._loop and self._loop.is_running():
            # Submit to existing loop and wait for result
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=30)  # 30 second timeout
        else:
            # No loop running, create new one
            return asyncio.run(coro)

    def is_async_context(self) -> bool:
        """Check if we're currently in an async context"""
        try:
            asyncio.current_task()
            return True
        except RuntimeError:
            return False

    def get_active_operations(self) -> Dict[str, Any]:
        """Get information about active operations"""
        with self._coordination_lock:
            return {
                "threads": {
                    tid: {
                        "operation": info.operation_name,
                        "duration": time.time() - info.start_time,
                        "daemon": info.is_daemon,
                        "mode": info.coordination_mode.value,
                    }
                    for tid, info in self._active_threads.items()
                },
                "async_tasks": len(self._async_tasks),
                "coordination_mode": self._coordination_mode.value,
                "loop_registered": self._loop is not None,
                "loop_thread": self._loop_thread_id,
            }

    async def graceful_shutdown(self, timeout: float = 30.0) -> bool:
        """Gracefully shutdown all operations"""
        if self.logger:
            self.logger.info("Starting graceful shutdown of thread coordinator")

        # Signal shutdown
        self._shutdown_event.set()

        start_time = time.time()

        # Wait for threads to complete
        while self._active_threads and (time.time() - start_time) < timeout:
            if self.logger:
                remaining = list(self._active_threads.values())
                self.logger.debug(f"Waiting for {len(remaining)} threads to complete")
            await asyncio.sleep(0.1)

        # Check if all operations completed
        with self._coordination_lock:
            remaining_operations = len(self._active_threads)
            if remaining_operations > 0:
                if self.logger:
                    self.logger.warning(
                        f"Shutdown timeout: {remaining_operations} operations still active"
                    )
                return False

        if self.logger:
            self.logger.info("Thread coordinator shutdown completed successfully")
        return True


class AsyncSyncBridge:
    """Bridge between async and sync code with proper coordination"""

    def __init__(self, coordinator: ThreadCoordinator):
        self.coordinator = coordinator
        self._bridges: Dict[str, Any] = {}

    def sync_method(
        self, async_method: Callable[..., Awaitable[T]]
    ) -> Callable[..., T]:
        """Convert async method to sync with coordination"""

        def wrapper(*args, **kwargs):
            coro = async_method(*args, **kwargs)
            return self.coordinator.run_async_from_sync(coro)

        wrapper.__name__ = f"sync_{async_method.__name__}"
        wrapper.__doc__ = f"Synchronous wrapper for {async_method.__name__}"
        return wrapper

    def async_method(
        self, sync_method: Callable[..., T]
    ) -> Callable[..., Awaitable[T]]:
        """Convert sync method to async with coordination"""

        async def wrapper(*args, **kwargs):
            return await self.coordinator.run_in_thread(sync_method, *args, **kwargs)

        wrapper.__name__ = f"async_{sync_method.__name__}"
        wrapper.__doc__ = f"Asynchronous wrapper for {sync_method.__name__}"
        return wrapper


@asynccontextmanager
async def async_thread_coordination(
    coordinator: ThreadCoordinator, operation_name: str
):
    """Async context manager for coordinated operations"""
    try:
        if coordinator.logger:
            coordinator.logger.debug(
                f"Starting coordinated async operation: {operation_name}"
            )
        yield coordinator
    finally:
        if coordinator.logger:
            coordinator.logger.debug(
                f"Completed coordinated async operation: {operation_name}"
            )


class ThreadSafeAsyncQueue:
    """Thread-safe queue that works with both async and sync code"""

    def __init__(self, maxsize: int = 0):
        self._async_queue = asyncio.Queue(maxsize=maxsize)
        self._sync_queue = asyncio.Queue(maxsize=maxsize)
        self._coordinator = ThreadCoordinator()

    async def async_put(self, item: T) -> None:
        """Put item from async context"""
        await self._async_queue.put(item)

    async def async_get(self) -> T:
        """Get item from async context"""
        return await self._async_queue.get()

    def sync_put(self, item: T, timeout: Optional[float] = None) -> None:
        """Put item from sync context"""

        async def _put():
            await self._async_queue.put(item)

        self._coordinator.run_async_from_sync(_put())

    def sync_get(self, timeout: Optional[float] = None) -> T:
        """Get item from sync context"""

        async def _get():
            return await self._async_queue.get()

        return self._coordinator.run_async_from_sync(_get())

    def qsize(self) -> int:
        """Get queue size (thread-safe)"""
        return self._async_queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty (thread-safe)"""
        return self._async_queue.empty()

    def full(self) -> bool:
        """Check if queue is full (thread-safe)"""
        return self._async_queue.full()


# Global thread coordinator instance
_global_coordinator: Optional[ThreadCoordinator] = None


def get_thread_coordinator() -> ThreadCoordinator:
    """Get the global thread coordinator instance"""
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = ThreadCoordinator()
    return _global_coordinator


def configure_coordination_mode(mode: CoordinationMode) -> None:
    """Configure the global coordination mode"""
    coordinator = get_thread_coordinator()
    coordinator.set_coordination_mode(mode)


async def ensure_async_context():
    """Ensure we're in an async context, registering the loop if needed"""
    coordinator = get_thread_coordinator()
    if not coordinator._loop:
        coordinator.register_async_loop()


def mixed_operation(
    async_func: Optional[Callable] = None, sync_func: Optional[Callable] = None
):
    """Decorator for operations that can work in both async and sync contexts"""

    def decorator(func):
        coordinator = get_thread_coordinator()

        if coordinator.is_async_context():
            return async_func(func) if async_func else func
        else:
            return sync_func(func) if sync_func else func

    return decorator
