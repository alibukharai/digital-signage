"""
Service registrars for cleaner dependency injection setup
Following DIP principle by providing different configurations
"""

from abc import ABC, abstractmethod
from typing import Protocol

from ..domain.configuration import ProvisioningConfig
from ..interfaces import (
    IBluetoothService,
    IConfigurationService,
    IDeviceInfoProvider,
    IDisplayService,
    IFactoryResetService,
    IHealthMonitor,
    ILogger,
    INetworkService,
    IOwnershipService,
    ISecurityService,
)
from .dependency_injection import Container


class IServiceRegistrar(Protocol):
    """Protocol for service registration"""

    def register_services(
        self, container: Container, config: ProvisioningConfig
    ) -> None:
        """Register services in the container"""
        ...


class CoreServicesRegistrar:
    """Registers production services"""

    def register_services(
        self, container: Container, config: ProvisioningConfig
    ) -> None:
        """Register core production services"""
        from ..infrastructure import (
            BluetoothService,
            ConfigurationService,
            DeviceInfoProvider,
            DisplayService,
            FactoryResetService,
            HealthMonitorService,
            LoggingService,
            NetworkService,
            OwnershipService,
            SecurityService,
        )

        # Register logging first as other services depend on it
        container.register_singleton(
            ILogger, LoggingService, lambda c: LoggingService(config.logging)
        )

        # Get logger for other services
        logger = container.resolve(ILogger)

        # Register infrastructure services
        container.register_singleton(
            IDeviceInfoProvider,
            DeviceInfoProvider,
            lambda c: DeviceInfoProvider(config.system, logger),
        )

        container.register_singleton(
            INetworkService,
            NetworkService,
            lambda c: NetworkService(config.network, logger),
        )

        container.register_singleton(
            IBluetoothService,
            BluetoothService,
            lambda c: BluetoothService(config.ble, logger),
        )

        container.register_singleton(
            IDisplayService,
            DisplayService,
            lambda c: DisplayService(config.display, logger),
        )

        container.register_singleton(
            ISecurityService,
            SecurityService,
            lambda c: SecurityService(config.security, logger),
        )

        container.register_singleton(
            IConfigurationService,
            ConfigurationService,
            lambda c: ConfigurationService(logger=logger),
        )

        container.register_singleton(
            IOwnershipService,
            OwnershipService,
            lambda c: OwnershipService(config.security, logger),
        )

        container.register_singleton(
            IFactoryResetService,
            FactoryResetService,
            lambda c: FactoryResetService(config.system, logger),
        )

        container.register_singleton(
            IHealthMonitor,
            HealthMonitorService,
            lambda c: HealthMonitorService(config.system, logger),
        )


class TestServicesRegistrar:
    """Registers test services with LSP-compliant implementations"""

    def register_services(
        self, container: Container, config: ProvisioningConfig
    ) -> None:
        """Register test services with predictable implementations"""
        # Import test doubles from tests module (proper separation of concerns)
        try:
            from tests.test_doubles import (
                TestBluetoothService,
                TestConfigurationService,
                TestDeviceInfoProvider,
                TestDisplayService,
                TestFactoryResetService,
                TestHealthMonitorService,
                TestLogger,
                TestNetworkService,
                TestOwnershipService,
                TestSecurityService,
            )
        except ImportError:
            # Fallback to mock services if test doubles not available
            from unittest.mock import Mock

            # Create mock logger
            test_logger = Mock(spec=ILogger)
            container.register_instance(ILogger, test_logger)

            # Register mock services (less ideal but works)
            for interface in [
                INetworkService,
                IBluetoothService,
                IDisplayService,
                IConfigurationService,
                ISecurityService,
                IDeviceInfoProvider,
                IOwnershipService,
                IFactoryResetService,
                IHealthMonitor,
            ]:
                mock_service = Mock(spec=interface)
                container.register_instance(interface, mock_service)
            return

        # Register test logger
        test_logger = TestLogger()
        container.register_instance(ILogger, test_logger)

        # Register test services with consistent LSP-compliant behavior
        container.register_singleton(
            INetworkService,
            TestNetworkService,
            lambda c: TestNetworkService(test_logger),
        )

        container.register_singleton(
            IBluetoothService,
            TestBluetoothService,
            lambda c: TestBluetoothService(test_logger),
        )

        container.register_singleton(
            IDisplayService,
            TestDisplayService,
            lambda c: TestDisplayService(test_logger),
        )

        container.register_singleton(
            IConfigurationService,
            TestConfigurationService,
            lambda c: TestConfigurationService(test_logger),
        )

        # Register remaining services with proper test implementations
        container.register_singleton(
            IDeviceInfoProvider,
            TestDeviceInfoProvider,
            lambda c: TestDeviceInfoProvider(test_logger),
        )

        container.register_singleton(
            ISecurityService,
            TestSecurityService,
            lambda c: TestSecurityService(test_logger),
        )

        container.register_singleton(
            IOwnershipService,
            TestOwnershipService,
            lambda c: TestOwnershipService(test_logger),
        )

        container.register_singleton(
            IFactoryResetService,
            TestFactoryResetService,
            lambda c: TestFactoryResetService(test_logger),
        )

        container.register_singleton(
            IHealthMonitor,
            TestHealthMonitorService,
            lambda c: TestHealthMonitorService(test_logger),
        )


class DevServicesRegistrar:
    """Registers development services with enhanced logging and debugging"""

    def register_services(
        self, container: Container, config: ProvisioningConfig
    ) -> None:
        """Register development services"""
        # Use core services but with development config overrides
        dev_config = config
        dev_config.logging.level = "DEBUG"
        dev_config.logging.console_output = True

        # Register core services
        core_registrar = CoreServicesRegistrar()
        core_registrar.register_services(container, dev_config)


class ServiceRegistrarFactory:
    """Factory for creating appropriate service registrar"""

    @staticmethod
    def create_registrar(environment: str = "production") -> IServiceRegistrar:
        """Create registrar based on environment"""
        registrars = {
            "production": CoreServicesRegistrar(),
            "development": DevServicesRegistrar(),
            "test": TestServicesRegistrar(),
        }

        return registrars.get(environment, CoreServicesRegistrar())


def create_configured_container(
    config: ProvisioningConfig, environment: str = "production"
) -> Container:
    """Create a fully configured container"""
    container = Container()

    # Get appropriate registrar
    registrar = ServiceRegistrarFactory.create_registrar(environment)

    # Register services
    registrar.register_services(container, config)

    return container
