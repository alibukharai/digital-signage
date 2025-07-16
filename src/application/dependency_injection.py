"""
Dependency injection container for the application layer
"""

import inspect
import weakref
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

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
        """Resolve a service with enhanced error handling"""
        with self._lock:
            try:
                if service_type not in self._services:
                    available_services = [s.__name__ for s in self._services.keys()]
                    raise ValueError(
                        f"Service {service_type.__name__} is not registered. "
                        f"Available services: {available_services}"
                    )

                descriptor = self._services[service_type]

                # Return existing instance if available
                if descriptor.instance is not None:
                    return descriptor.instance

                # Check singleton cache
                if descriptor.lifetime == ServiceLifetime.SINGLETON:
                    if service_type in self._singletons:
                        return self._singletons[service_type]

                # Pre-check for circular dependencies before attempting creation
                try:
                    self._check_circular_dependencies(service_type, set())
                except ValueError as circular_error:
                    raise ValueError(
                        f"Cannot resolve {service_type.__name__}: {circular_error}"
                    )

                # Create new instance
                instance = self._create_instance(descriptor)

                # Cache singleton
                if descriptor.lifetime == ServiceLifetime.SINGLETON:
                    self._singletons[service_type] = instance

                return instance

            except Exception as e:
                # Enhanced error context for resolution failures
                if "Cannot resolve" in str(e) or "Circular dependency" in str(e):
                    raise  # Re-raise with existing context
                else:
                    raise ValueError(
                        f"Service resolution failed for {service_type.__name__}: "
                        f"{type(e).__name__}: {str(e)}"
                    )

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
        """Create an instance from descriptor with improved error handling and circular dependency detection"""
        # Check for circular dependencies
        if hasattr(self, "_resolution_stack"):
            if descriptor.service_type in self._resolution_stack:
                dependency_chain = " -> ".join(
                    [t.__name__ for t in self._resolution_stack]
                )
                raise ValueError(
                    f"Circular dependency detected: {dependency_chain} -> {descriptor.service_type.__name__}"
                )
        else:
            self._resolution_stack = set()

        # Add current type to resolution stack
        self._resolution_stack.add(descriptor.service_type)

        try:
            if descriptor.factory:
                return descriptor.factory(self)
            elif descriptor.implementation_type:
                return self._create_with_dependency_injection(descriptor)
            else:
                # Try to instantiate the service type directly
                try:
                    return descriptor.service_type()
                except Exception as e:
                    raise ValueError(
                        f"Failed to instantiate service {descriptor.service_type.__name__}: {str(e)}"
                    )
        finally:
            # Remove from resolution stack
            if hasattr(self, "_resolution_stack"):
                self._resolution_stack.discard(descriptor.service_type)
                if not self._resolution_stack:
                    delattr(self, "_resolution_stack")

    def _create_with_dependency_injection(self, descriptor: ServiceDescriptor) -> Any:
        """Create instance with simplified and more robust dependency injection"""

        try:
            sig = inspect.signature(descriptor.implementation_type.__init__)
            params = list(sig.parameters.values())[1:]  # Skip 'self'

            if not params:
                # No dependencies needed
                return descriptor.implementation_type()

            # Resolve dependencies with better handling
            args = []
            kwargs = {}

            for param in params:
                param_name = param.name
                param_type = param.annotation
                has_default = param.default != inspect.Parameter.empty

                # Handle parameters without type annotations
                if param_type == inspect.Parameter.empty:
                    if has_default:
                        # Use default value for remaining parameters
                        break
                    else:
                        raise ValueError(
                            f"Parameter '{param_name}' in {descriptor.implementation_type.__name__} "
                            f"has no type annotation and no default value. "
                            f"Cannot perform dependency injection without type information."
                        )

                # Try to resolve the dependency
                try:
                    dependency = self.resolve(param_type)
                    args.append(dependency)
                except ValueError as dependency_error:
                    if has_default:
                        # Parameter has default value - use it and stop processing positional args
                        # Switch to keyword arguments for remaining parameters if needed
                        break
                    else:
                        # Required dependency not found - provide detailed error
                        available_services = [
                            service.__name__ for service in self._services.keys()
                        ]
                        raise ValueError(
                            f"Cannot resolve required dependency '{param_type.__name__}' "
                            f"for parameter '{param_name}' in {descriptor.implementation_type.__name__}. "
                            f"Available services: {available_services}. "
                            f"Original error: {dependency_error}"
                        )

            # Create instance with resolved dependencies
            try:
                instance = descriptor.implementation_type(*args, **kwargs)
                return instance
            except TypeError as type_error:
                # Provide better error message for constructor issues
                raise ValueError(
                    f"Failed to instantiate {descriptor.implementation_type.__name__} "
                    f"with resolved dependencies. Constructor signature mismatch: {type_error}"
                )

        except Exception as e:
            # Provide detailed error message with context
            if "Cannot resolve dependency" in str(e) or "Circular dependency" in str(e):
                raise  # Re-raise dependency resolution errors with full context
            elif "Constructor signature mismatch" in str(e):
                raise  # Re-raise constructor errors
            else:
                # Unexpected error during dependency injection
                raise ValueError(
                    f"Unexpected error during dependency injection for {descriptor.implementation_type.__name__}: "
                    f"{type(e).__name__}: {str(e)}"
                )

    def clear(self) -> None:
        """Clear all registrations"""
        with self._lock:
            self._services.clear()
            self._singletons.clear()

    def validate_registrations(self) -> Dict[str, Any]:
        """Validate all registrations for potential issues"""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "service_count": len(self._services),
            "singleton_count": len(self._singletons),
        }

        # Check for circular dependencies without creating instances
        for service_type, descriptor in self._services.items():
            try:
                self._check_circular_dependencies(service_type, set())
            except ValueError as e:
                validation_results["valid"] = False
                validation_results["errors"].append(str(e))

        # Check for missing dependencies
        for service_type, descriptor in self._services.items():
            if descriptor.implementation_type:
                missing_deps = self._check_missing_dependencies(
                    descriptor.implementation_type
                )
                if missing_deps:
                    validation_results["warnings"].append(
                        f"Service {service_type.__name__} has unregistered dependencies: {missing_deps}"
                    )

        return validation_results

    def _check_circular_dependencies(
        self, service_type: Type, resolution_path: set
    ) -> None:
        """Check for circular dependencies in service resolution"""
        if service_type in resolution_path:
            path_list = list(resolution_path) + [service_type]
            path_names = " -> ".join([t.__name__ for t in path_list])
            raise ValueError(f"Circular dependency detected: {path_names}")

        if service_type not in self._services:
            # Service not registered, can't check dependencies
            return

        descriptor = self._services[service_type]

        # Only check implementation types (not factories or instances)
        if not descriptor.implementation_type:
            return

        # Add current service to resolution path
        new_path = resolution_path | {service_type}

        # Get constructor parameters
        try:
            signature = inspect.signature(descriptor.implementation_type.__init__)
            params = [p for name, p in signature.parameters.items() if name != "self"]

            for param in params:
                param_type = param.annotation

                # Skip parameters without type annotations or with defaults
                if (
                    param_type == inspect.Parameter.empty
                    or param.default != inspect.Parameter.empty
                ):
                    continue

                # Recursively check dependencies
                self._check_circular_dependencies(param_type, new_path)

        except Exception:
            # If we can't inspect the constructor, skip circular dependency check
            pass

    def _check_missing_dependencies(self, implementation_type: Type) -> List[str]:
        """Check for missing dependencies in a service implementation"""
        missing_deps = []

        try:
            signature = inspect.signature(implementation_type.__init__)
            params = [p for name, p in signature.parameters.items() if name != "self"]

            for param in params:
                param_type = param.annotation

                # Skip parameters without type annotations or with defaults
                if (
                    param_type == inspect.Parameter.empty
                    or param.default != inspect.Parameter.empty
                ):
                    continue

                # Check if dependency is registered
                if param_type not in self._services:
                    missing_deps.append(param_type.__name__)

        except Exception:
            # If we can't inspect the constructor, return empty list
            pass

        return missing_deps

    def dispose(self) -> None:
        """Dispose of all services and clear resources"""
        with self._lock:
            try:
                # Dispose of singleton instances that support disposal
                disposed_count = 0
                for service_type, instance in self._singletons.items():
                    try:
                        # Check if instance has dispose method
                        if hasattr(instance, "dispose"):
                            instance.dispose()
                            disposed_count += 1
                        elif hasattr(instance, "close"):
                            instance.close()
                            disposed_count += 1
                        elif hasattr(instance, "__exit__"):
                            # Context manager - call exit
                            instance.__exit__(None, None, None)
                            disposed_count += 1
                    except Exception as dispose_error:
                        # Log disposal errors but continue with cleanup
                        # Note: We don't have logger access here, so we'll silently continue
                        pass

                # Clear all collections
                self._services.clear()
                self._singletons.clear()

            except Exception:
                # Ensure cleanup even if disposal fails
                self._services.clear()
                self._singletons.clear()

    def __enter__(self) -> "Container":
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with automatic disposal"""
        self.dispose()

    def get_service_info(self, service_type: Type) -> Optional[Dict[str, Any]]:
        """Get information about a registered service"""
        if service_type not in self._services:
            return None

        descriptor = self._services[service_type]

        info = {
            "service_type": service_type.__name__,
            "lifetime": descriptor.lifetime,
            "has_instance": descriptor.instance is not None,
            "is_singleton_cached": service_type in self._singletons,
            "implementation_type": descriptor.implementation_type.__name__
            if descriptor.implementation_type
            else None,
            "has_factory": descriptor.factory is not None,
        }

        # Add dependency information
        if descriptor.implementation_type:
            try:
                signature = inspect.signature(descriptor.implementation_type.__init__)
                params = [
                    p for name, p in signature.parameters.items() if name != "self"
                ]

                dependencies = []
                for param in params:
                    if param.annotation != inspect.Parameter.empty:
                        dependencies.append(
                            {
                                "name": param.name,
                                "type": param.annotation.__name__,
                                "has_default": param.default != inspect.Parameter.empty,
                                "is_registered": param.annotation in self._services,
                            }
                        )

                info["dependencies"] = dependencies

            except Exception:
                info["dependencies"] = []

        return info

    def get_all_service_info(self) -> Dict[str, Any]:
        """Get information about all registered services"""
        return {
            "service_count": len(self._services),
            "singleton_count": len(self._singletons),
            "services": {
                service_type.__name__: self.get_service_info(service_type)
                for service_type in self._services.keys()
            },
        }
