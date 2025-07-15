"""
Dependency injection container for the application layer
"""

import weakref
from threading import Lock
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

T = TypeVar("T")


class ServiceLifetime:
    """Service lifetime constants"""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceDescriptor:
    """Describes how a service should be created"""

    def __init__(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[["Container"], T]] = None,
        instance: Optional[T] = None,
        lifetime: str = ServiceLifetime.SINGLETON,
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime


class Container:
    """Dependency injection container"""

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = Lock()

    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[["Container"], T]] = None,
    ) -> "Container":
        """Register a service as singleton"""
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation_type,
                factory=factory,
                lifetime=ServiceLifetime.SINGLETON,
            )
            self._services[service_type] = descriptor
        return self

    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[["Container"], T]] = None,
    ) -> "Container":
        """Register a service as transient"""
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=implementation_type,
                factory=factory,
                lifetime=ServiceLifetime.TRANSIENT,
            )
            self._services[service_type] = descriptor
        return self

    def register_instance(self, service_type: Type[T], instance: T) -> "Container":
        """Register an existing instance"""
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                instance=instance,
                lifetime=ServiceLifetime.SINGLETON,
            )
            self._services[service_type] = descriptor
            self._singletons[service_type] = instance
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} is not registered")

        descriptor = self._services[service_type]

        # Return existing instance if available
        if descriptor.instance is not None:
            return descriptor.instance

        # Check singleton cache
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

        # Create new instance
        instance = self._create_instance(descriptor)

        # Cache singleton
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            with self._lock:
                self._singletons[service_type] = instance

        return instance

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """Try to resolve a service, return None if not found"""
        try:
            return self.resolve(service_type)
        except ValueError:
            return None

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service is registered"""
        return service_type in self._services

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance from descriptor"""
        if descriptor.factory:
            return descriptor.factory(self)
        elif descriptor.implementation_type:
            # Try to inject dependencies if constructor needs them
            try:
                import inspect

                sig = inspect.signature(descriptor.implementation_type.__init__)
                params = list(sig.parameters.values())[1:]  # Skip 'self'

                if params:
                    # Try to resolve dependencies
                    args = []
                    for param in params:
                        if param.annotation != inspect.Parameter.empty:
                            try:
                                dependency = self.resolve(param.annotation)
                                args.append(dependency)
                            except ValueError:
                                # If dependency not found, skip or use default
                                if param.default != inspect.Parameter.empty:
                                    break
                                else:
                                    raise
                    return descriptor.implementation_type(*args)
                else:
                    return descriptor.implementation_type()
            except:
                # Fallback to simple instantiation
                return descriptor.implementation_type()
        else:
            return descriptor.service_type()

    def clear(self) -> None:
        """Clear all registrations"""
        with self._lock:
            self._services.clear()
            self._singletons.clear()


# Global container instance
_container: Optional[Container] = None
_container_lock = Lock()


def get_container() -> Container:
    """Get the global container instance"""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container"""
    global _container
    with _container_lock:
        _container = None
