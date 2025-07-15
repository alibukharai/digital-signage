"""
Main orchestrator for the provisioning system
"""

import asyncio
import signal
import sys
from typing import Optional, Dict, Any
from ..interfaces import (
    INetworkService, IBluetoothService, IDisplayService, ISecurityService,
    IConfigurationService, IOwnershipService, IFactoryResetService,
    IHealthMonitor, ILogger, IDeviceInfoProvider, DeviceState
)
from ..domain.events import EventBus, EventType, get_event_bus
from ..domain.validation import ValidationService
from ..domain.state import ProvisioningStateMachine, ProvisioningEvent
from ..domain.configuration import ProvisioningConfig
from .dependency_injection import Container
from .use_cases import (
    NetworkProvisioningUseCase,
    OwnerSetupUseCase,
    FactoryResetUseCase,
    SystemHealthUseCase
)


class ProvisioningOrchestrator:
    """Main orchestrator for the provisioning system"""
    
    def __init__(self, config: ProvisioningConfig, container: Container):
        self.config = config
        self.container = container
        
        # Get services from container
        self.logger = container.resolve(ILogger)
        self.device_info_provider = container.resolve(IDeviceInfoProvider)
        self.network_service = container.resolve(INetworkService)
        self.bluetooth_service = container.resolve(IBluetoothService)
        self.display_service = container.resolve(IDisplayService)
        self.security_service = container.resolve(ISecurityService)
        self.config_service = container.resolve(IConfigurationService)
        self.ownership_service = container.resolve(IOwnershipService)
        self.factory_reset_service = container.resolve(IFactoryResetService)
        self.health_monitor = container.resolve(IHealthMonitor)
        
        # Create domain services
        self.event_bus = get_event_bus()
        self.validation_service = ValidationService(self.logger)
        self.state_machine = ProvisioningStateMachine(self.event_bus, self.logger)
        
        # Create use cases
        self.network_provisioning = NetworkProvisioningUseCase(
            self.network_service,
            self.bluetooth_service,
            self.display_service,
            self.security_service,
            self.config_service,
            self.validation_service,
            self.event_bus,
            self.state_machine,
            self.logger
        )
        
        self.owner_setup = OwnerSetupUseCase(
            self.ownership_service,
            self.security_service,
            self.validation_service,
            self.event_bus,
            self.logger
        )
        
        self.factory_reset = FactoryResetUseCase(
            self.factory_reset_service,
            self.ownership_service,
            self.config_service,
            self.event_bus,
            self.logger
        )
        
        self.system_health = SystemHealthUseCase(
            self.health_monitor,
            self.event_bus,
            self.logger
        )
        
        # State tracking
        self.is_running = False
        self.background_tasks = []
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Provisioning orchestrator initialized")
    
    async def start(self) -> bool:
        """Start the provisioning system"""
        try:
            self.is_running = True
            self.logger.info("Starting Rock Pi 3399 provisioning system")
            
            # Get device information
            device_info = self.device_info_provider.get_device_info()
            self.logger.info(f"Device ID: {device_info.device_id}")
            self.logger.info(f"MAC Address: {device_info.mac_address}")
            
            # Start background services
            await self._start_background_services()
            
            # Check if network is already configured
            if self.network_service.is_connected():
                self.logger.info("Device already connected to network")
                self.state_machine.process_event(ProvisioningEvent.NETWORK_CONNECTED)
                return True
            
            # Check owner setup requirements
            if self.config.security.require_owner_setup and not self.owner_setup.is_owner_registered():
                self.logger.info("Starting owner setup mode")
                if not self.owner_setup.start_setup():
                    self.logger.error("Failed to start owner setup")
                    return False
                
                # Wait for owner registration (in real implementation, this would be event-driven)
                await self._wait_for_owner_setup()
            
            # Start network provisioning
            self.logger.info("Starting network provisioning")
            success = await self.network_provisioning.start_provisioning(device_info)
            
            if success:
                # Wait for provisioning to complete
                await self._wait_for_provisioning()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to start provisioning system: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the provisioning system"""
        try:
            self.logger.info("Stopping provisioning system")
            self.is_running = False
            
            # Stop provisioning
            await self.network_provisioning.stop_provisioning()
            
            # Stop background services
            await self._stop_background_services()
            
            # Cancel background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            self.logger.info("Provisioning system stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping provisioning system: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            return {
                'state': self.state_machine.get_current_state().value,
                'running': self.is_running,
                'device_info': {
                    'device_id': self.device_info_provider.get_device_id(),
                    'mac_address': self.device_info_provider.get_mac_address()
                },
                'network': {
                    'connected': self.network_service.is_connected(),
                    'connection_info': self.network_service.get_connection_info().__dict__
                },
                'bluetooth': {
                    'advertising': self.bluetooth_service.is_advertising()
                },
                'display': {
                    'active': self.display_service.is_display_active()
                },
                'owner': {
                    'registered': self.owner_setup.is_owner_registered(),
                    'setup_info': self.owner_setup.get_setup_info()
                },
                'factory_reset': {
                    'available': self.factory_reset.is_reset_available(),
                    'info': self.factory_reset.get_reset_info()
                },
                'health': self.system_health.get_health_status()
            }
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}
    
    async def _start_background_services(self) -> None:
        """Start background services"""
        try:
            # Start health monitoring
            self.system_health.start_monitoring()
            
            # Start factory reset monitoring if available
            if hasattr(self.factory_reset_service, 'start_monitoring'):
                self.factory_reset_service.start_monitoring(self._on_factory_reset_triggered)
            
            self.logger.info("Background services started")
            
        except Exception as e:
            self.logger.error(f"Failed to start background services: {e}")
    
    async def _stop_background_services(self) -> None:
        """Stop background services"""
        try:
            # Stop health monitoring
            self.system_health.stop_monitoring()
            
            # Stop factory reset monitoring
            if hasattr(self.factory_reset_service, 'stop_monitoring'):
                self.factory_reset_service.stop_monitoring()
            
            self.logger.info("Background services stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping background services: {e}")
    
    async def _wait_for_owner_setup(self) -> None:
        """Wait for owner setup to complete"""
        timeout = self.config.security.owner_setup_timeout
        elapsed = 0
        
        while elapsed < timeout and not self.owner_setup.is_owner_registered():
            await asyncio.sleep(1)
            elapsed += 1
        
        if self.owner_setup.is_owner_registered():
            self.logger.info("Owner setup completed")
            self.state_machine.process_event(ProvisioningEvent.OWNER_REGISTERED)
        else:
            self.logger.warning("Owner setup timed out")
            self.state_machine.process_event(ProvisioningEvent.TIMEOUT)
    
    async def _wait_for_provisioning(self) -> None:
        """Wait for network provisioning to complete"""
        timeout = self.config.system.provisioning_timeout
        elapsed = 0
        
        while (elapsed < timeout and 
               self.state_machine.get_current_state() not in [DeviceState.CONNECTED, DeviceState.ERROR] and
               self.is_running):
            await asyncio.sleep(1)
            elapsed += 1
        
        if self.state_machine.get_current_state() == DeviceState.CONNECTED:
            self.logger.info("Network provisioning completed successfully")
            self.state_machine.process_event(ProvisioningEvent.PROVISIONING_COMPLETE)
        elif elapsed >= timeout:
            self.logger.warning("Network provisioning timed out")
            self.state_machine.process_event(ProvisioningEvent.TIMEOUT)
    
    def _on_factory_reset_triggered(self) -> None:
        """Handle factory reset trigger"""
        try:
            self.logger.critical("Factory reset triggered")
            self.state_machine.process_event(ProvisioningEvent.RESET_TRIGGERED)
            
            # Publish event
            self.event_bus.publish(
                EventType.FACTORY_RESET_TRIGGERED,
                {'triggered_by': 'hardware_button'},
                'orchestrator'
            )
            
        except Exception as e:
            self.logger.error(f"Error handling factory reset: {e}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully")
        asyncio.create_task(self.stop())


async def main() -> int:
    """Main entry point"""
    try:
        # Load configuration
        from ..domain.configuration import load_config
        config = load_config()
        
        # Setup container with services
        container = Container()
        
        # Register infrastructure services
        from ..infrastructure import (
            LoggingService, NetworkService, BluetoothService, DisplayService,
            SecurityService, ConfigurationService, DeviceInfoProvider,
            HealthMonitorService, OwnershipService, FactoryResetService
        )
        from ..interfaces import (
            ILogger, IDeviceInfoProvider, INetworkService, IBluetoothService,
            IDisplayService, ISecurityService, IConfigurationService,
            IOwnershipService, IFactoryResetService, IHealthMonitor
        )
        
        # Register services with proper factories
        container.register_instance(ILogger, LoggingService(config.logging))
        
        container.register_singleton(
            IDeviceInfoProvider, 
            DeviceInfoProvider, 
            lambda c: DeviceInfoProvider(c.resolve(ILogger))
        )
        
        container.register_singleton(
            INetworkService, 
            NetworkService,
            lambda c: NetworkService(config.network, c.resolve(ILogger))
        )
        
        container.register_singleton(
            IBluetoothService, 
            BluetoothService,
            lambda c: BluetoothService(config.ble, c.resolve(ILogger))
        )
        
        container.register_singleton(
            IDisplayService, 
            DisplayService,
            lambda c: DisplayService(config.display, c.resolve(ILogger))
        )
        
        container.register_singleton(
            ISecurityService, 
            SecurityService,
            lambda c: SecurityService(config.security, c.resolve(ILogger))
        )
        
        container.register_singleton(
            IConfigurationService, 
            ConfigurationService,
            lambda c: ConfigurationService(c.resolve(ILogger))
        )
        
        container.register_singleton(
            IOwnershipService, 
            OwnershipService,
            lambda c: OwnershipService(config.security, c.resolve(ILogger))
        )
        
        container.register_singleton(
            IFactoryResetService, 
            FactoryResetService,
            lambda c: FactoryResetService(config.system.factory_reset_pin, c.resolve(ILogger))
        )
        
        container.register_singleton(
            IHealthMonitor, 
            HealthMonitorService,
            lambda c: HealthMonitorService(config.system.health_check_interval, c.resolve(ILogger))
        )
        
        # Create and run orchestrator
        orchestrator = ProvisioningOrchestrator(config, container)
        success = await orchestrator.start()
        
        if success:
            # Keep running until interrupted
            try:
                while orchestrator.is_running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
        
        await orchestrator.stop()
        return 0 if success else 1
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
