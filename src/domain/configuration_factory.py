"""
Configuration loading abstraction that follows OCP
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from ..domain.configuration import ProvisioningConfig


class IConfigurationLoader(ABC):
    """Abstract configuration loader interface"""

    @abstractmethod
    def can_load(self, path: str) -> bool:
        """Check if this loader can handle the given path"""
        pass

    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        """Load configuration from path"""
        pass


class JsonConfigurationLoader(IConfigurationLoader):
    """JSON configuration loader"""

    def can_load(self, path: str) -> bool:
        return path.endswith(".json")

    def load(self, path: str) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)


class YamlConfigurationLoader(IConfigurationLoader):
    """YAML configuration loader (example extension)"""

    def can_load(self, path: str) -> bool:
        return path.endswith((".yaml", ".yml"))

    def load(self, path: str) -> Dict[str, Any]:
        try:
            import yaml

            with open(path, "r") as f:
                return yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML required for YAML configuration")


class ConfigurationLoaderRegistry:
    """Registry for configuration loaders"""

    def __init__(self):
        self._loaders = []

    def register_loader(self, loader: IConfigurationLoader):
        """Register a new configuration loader"""
        self._loaders.append(loader)

    def get_loader(self, path: str) -> Optional[IConfigurationLoader]:
        """Get appropriate loader for path"""
        for loader in self._loaders:
            if loader.can_load(path):
                return loader
        return None


class ConfigurationFactory:
    """Factory for creating configurations with extensible loading"""

    def __init__(self):
        self.registry = ConfigurationLoaderRegistry()
        # Register default loaders
        self.registry.register_loader(JsonConfigurationLoader())
        # self.registry.register_loader(YamlConfigurationLoader())  # Optional

    def load_config(self, config_path: Optional[str] = None) -> ProvisioningConfig:
        """Load configuration using appropriate loader"""
        if config_path is None:
            config_path = self._find_config_file()

        if config_path and Path(config_path).exists():
            loader = self.registry.get_loader(config_path)
            if loader:
                try:
                    data = loader.load(config_path)
                    return self._create_config_from_data(data)
                except Exception as e:
                    # Log error and fall back to default
                    print(f"Failed to load config from {config_path}: {e}")

        return ProvisioningConfig()  # Default configuration

    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations"""
        possible_paths = [
            "/etc/rockpi-provisioning/config.json",
            "config/unified_config.json",
            "config.json",
            "/etc/rockpi-provisioning/config.yaml",  # Support for future YAML
            "config/unified_config.yaml",
            "config.yaml",
        ]

        for path in possible_paths:
            if Path(path).exists():
                return path
        return None

    def _create_config_from_data(self, data: Dict[str, Any]) -> ProvisioningConfig:
        """Create ProvisioningConfig from loaded data"""
        # This method can be enhanced to handle various data transformations
        return ProvisioningConfig.from_dict(data)
