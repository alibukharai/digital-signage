"""
Command pattern implementation for operations
Following SOLID principles for extensible and testable operations
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..common.result_handling import Result
from ..domain.errors import ProvisioningError
from ..interfaces import IConfigurationService, ILogger, INetworkService


class ICommand(ABC):
    """Interface for commands"""

    @abstractmethod
    def execute(self) -> Result[Any, Exception]:
        """Execute the command"""
        pass

    @abstractmethod
    def undo(self) -> Result[Any, Exception]:
        """Undo the command (if supported)"""
        pass

    @abstractmethod
    def can_undo(self) -> bool:
        """Check if command can be undone"""
        pass


class BaseCommand(ICommand):
    """Base command with common functionality"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.executed = False
        self.execution_result: Optional[Result] = None

    def _log_info(self, message: str) -> None:
        """Log info message"""
        if self.logger:
            self.logger.info(message)

    def _log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message"""
        if self.logger:
            if exception:
                self.logger.error(f"{message}: {exception}")
            else:
                self.logger.error(message)

    def execute(self) -> Result[Any, Exception]:
        """Template method for execution"""
        try:
            self._log_info(f"Executing command: {self.__class__.__name__}")
            result = self._do_execute()
            self.executed = True
            self.execution_result = result

            if result.is_success():
                self._log_info(
                    f"Command executed successfully: {self.__class__.__name__}"
                )
            else:
                self._log_error(
                    f"Command failed: {self.__class__.__name__}", result.error
                )

            return result
        except Exception as e:
            self._log_error(f"Command execution error: {self.__class__.__name__}", e)
            return Result.failure(e)

    def undo(self) -> Result[Any, Exception]:
        """Template method for undo"""
        if not self.can_undo():
            return Result.failure(Exception("Command cannot be undone"))

        try:
            self._log_info(f"Undoing command: {self.__class__.__name__}")
            result = self._do_undo()

            if result.is_success():
                self.executed = False
                self._log_info(
                    f"Command undone successfully: {self.__class__.__name__}"
                )
            else:
                self._log_error(
                    f"Command undo failed: {self.__class__.__name__}", result.error
                )

            return result
        except Exception as e:
            self._log_error(f"Command undo error: {self.__class__.__name__}", e)
            return Result.failure(e)

    def can_undo(self) -> bool:
        """Default implementation - can undo if executed successfully"""
        return (
            self.executed
            and self.execution_result
            and self.execution_result.is_success()
        )

    @abstractmethod
    def _do_execute(self) -> Result[Any, Exception]:
        """Subclass implementation of execute"""
        pass

    def _do_undo(self) -> Result[Any, Exception]:
        """Default undo implementation - subclasses can override"""
        return Result.failure(
            Exception(f"Undo not implemented for {self.__class__.__name__}")
        )


class ConnectToNetworkCommand(BaseCommand):
    """Command to connect to a network"""

    def __init__(
        self,
        network_service: INetworkService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ):
        super().__init__(logger)
        self.network_service = network_service
        self.ssid = ssid
        self.password = password
        self.previous_connection_info = None

    def _do_execute(self) -> Result[bool, Exception]:
        """Execute network connection"""
        try:
            # Store current connection for potential undo
            self.previous_connection_info = self.network_service.get_connection_info()

            # Attempt connection
            success = self.network_service.connect_to_network(self.ssid, self.password)

            if success:
                return Result.success(True)
            else:
                return Result.failure(
                    Exception(f"Failed to connect to network: {self.ssid}")
                )

        except Exception as e:
            return Result.failure(e)

    def _do_undo(self) -> Result[bool, Exception]:
        """Undo network connection"""
        try:
            # Disconnect from current network
            self.network_service.disconnect()

            # If there was a previous connection, attempt to restore it
            if (
                self.previous_connection_info
                and hasattr(self.previous_connection_info, "ssid")
                and self.previous_connection_info.ssid
            ):
                # Note: We can't restore the previous connection without the password
                # This is a limitation of the undo operation for network connections
                return Result.success(True)

            return Result.success(True)

        except Exception as e:
            return Result.failure(e)


class SaveNetworkConfigCommand(BaseCommand):
    """Command to save network configuration"""

    def __init__(
        self,
        config_service: IConfigurationService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ):
        super().__init__(logger)
        self.config_service = config_service
        self.ssid = ssid
        self.password = password
        self.previous_config = None

    def _do_execute(self) -> Result[bool, Exception]:
        """Execute configuration save"""
        try:
            # Store previous configuration for undo
            self.previous_config = self.config_service.load_network_config()

            # Save new configuration
            success = self.config_service.save_network_config(self.ssid, self.password)

            if success:
                return Result.success(True)
            else:
                return Result.failure(Exception("Failed to save network configuration"))

        except Exception as e:
            return Result.failure(e)

    def _do_undo(self) -> Result[bool, Exception]:
        """Undo configuration save"""
        try:
            if self.previous_config:
                # Restore previous configuration
                prev_ssid, prev_password = self.previous_config
                success = self.config_service.save_network_config(
                    prev_ssid, prev_password
                )
            else:
                # Clear configuration if there was none before
                success = self.config_service.clear_network_config()

            if success:
                return Result.success(True)
            else:
                return Result.failure(
                    Exception("Failed to restore previous configuration")
                )

        except Exception as e:
            return Result.failure(e)


class StartProvisioningCommand(BaseCommand):
    """Command to start provisioning process"""

    def __init__(
        self,
        network_service: INetworkService,
        config_service: IConfigurationService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ):
        super().__init__(logger)
        self.network_service = network_service
        self.config_service = config_service
        self.ssid = ssid
        self.password = password

        # Sub-commands
        self.connect_command = ConnectToNetworkCommand(
            network_service, ssid, password, logger
        )
        self.save_config_command = SaveNetworkConfigCommand(
            config_service, ssid, password, logger
        )

    def _do_execute(self) -> Result[bool, Exception]:
        """Execute provisioning process"""
        try:
            # Execute connection
            connect_result = self.connect_command.execute()
            if connect_result.is_failure():
                return Result.failure(connect_result.error)

            # Execute configuration save
            save_result = self.save_config_command.execute()
            if save_result.is_failure():
                # Undo connection if save fails
                self.connect_command.undo()
                return Result.failure(save_result.error)

            return Result.success(True)

        except Exception as e:
            return Result.failure(e)

    def _do_undo(self) -> Result[bool, Exception]:
        """Undo provisioning process"""
        try:
            # Undo in reverse order
            save_undo_result = self.save_config_command.undo()
            connect_undo_result = self.connect_command.undo()

            # Consider successful if either undo succeeds
            if save_undo_result.is_success() or connect_undo_result.is_success():
                return Result.success(True)
            else:
                return Result.failure(Exception("Failed to undo provisioning"))

        except Exception as e:
            return Result.failure(e)


class CommandInvoker:
    """Invoker for executing and managing commands"""

    def __init__(self, logger: Optional[ILogger] = None):
        self.logger = logger
        self.command_history: List[ICommand] = []
        self.current_position = -1

    def execute_command(self, command: ICommand) -> Result[Any, Exception]:
        """Execute a command and add to history"""
        result = command.execute()

        if result.is_success():
            # Clear any commands after current position (for redo functionality)
            self.command_history = self.command_history[: self.current_position + 1]

            # Add command to history
            self.command_history.append(command)
            self.current_position += 1

        return result

    def undo_last_command(self) -> Result[Any, Exception]:
        """Undo the last executed command"""
        if self.current_position < 0:
            return Result.failure(Exception("No commands to undo"))

        command = self.command_history[self.current_position]
        result = command.undo()

        if result.is_success():
            self.current_position -= 1

        return result

    def redo_next_command(self) -> Result[Any, Exception]:
        """Redo the next command in history"""
        if self.current_position >= len(self.command_history) - 1:
            return Result.failure(Exception("No commands to redo"))

        self.current_position += 1
        command = self.command_history[self.current_position]
        result = command.execute()

        if result.is_failure():
            self.current_position -= 1

        return result

    def clear_history(self) -> None:
        """Clear command history"""
        self.command_history.clear()
        self.current_position = -1

    def get_history(self) -> List[str]:
        """Get command history as list of command names"""
        return [command.__class__.__name__ for command in self.command_history]


class CommandFactory:
    """Factory for creating commands"""

    @staticmethod
    def create_connect_command(
        network_service: INetworkService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ) -> ConnectToNetworkCommand:
        """Create a connect to network command"""
        return ConnectToNetworkCommand(network_service, ssid, password, logger)

    @staticmethod
    def create_save_config_command(
        config_service: IConfigurationService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ) -> SaveNetworkConfigCommand:
        """Create a save configuration command"""
        return SaveNetworkConfigCommand(config_service, ssid, password, logger)

    @staticmethod
    def create_provisioning_command(
        network_service: INetworkService,
        config_service: IConfigurationService,
        ssid: str,
        password: str,
        logger: Optional[ILogger] = None,
    ) -> StartProvisioningCommand:
        """Create a complete provisioning command"""
        return StartProvisioningCommand(
            network_service, config_service, ssid, password, logger
        )


# Macro command for complex operations
class MacroCommand(BaseCommand):
    """Command that executes multiple sub-commands"""

    def __init__(self, commands: List[ICommand], logger: Optional[ILogger] = None):
        super().__init__(logger)
        self.commands = commands
        self.executed_commands: List[ICommand] = []

    def _do_execute(self) -> Result[bool, Exception]:
        """Execute all sub-commands"""
        self.executed_commands.clear()

        for command in self.commands:
            result = command.execute()

            if result.is_failure():
                # Undo all previously executed commands
                for executed_command in reversed(self.executed_commands):
                    executed_command.undo()
                return Result.failure(result.error)

            self.executed_commands.append(command)

        return Result.success(True)

    def _do_undo(self) -> Result[bool, Exception]:
        """Undo all sub-commands in reverse order"""
        for command in reversed(self.executed_commands):
            result = command.undo()
            if result.is_failure():
                self._log_error(
                    f"Failed to undo command: {command.__class__.__name__}",
                    result.error,
                )

        self.executed_commands.clear()
        return Result.success(True)
