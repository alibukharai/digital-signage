"""
SOC Registry for easy extensibility and platform support
This file provides a centralized registry for adding new SOC support
"""

from dataclasses import dataclass
from typing import Dict, List, Type

from .soc_specifications import (
    AllwinnerDetector,
    BroadcomDetector,
    MediaTekDetector,
    QualcommDetector,
    RockchipDetector,
    SOCDetector,
    SOCFamily,
    SOCSpecification,
)


@dataclass
class SOCRegistryEntry:
    """Registry entry for a SOC family"""

    family: SOCFamily
    detector_class: Type[SOCDetector]
    description: str
    manufacturer: str
    common_boards: List[str]


class SOCRegistry:
    """Central registry for SOC families and their detectors"""

    # Registry of supported SOC families
    REGISTERED_FAMILIES: Dict[SOCFamily, SOCRegistryEntry] = {
        SOCFamily.ROCKCHIP: SOCRegistryEntry(
            family=SOCFamily.ROCKCHIP,
            detector_class=RockchipDetector,
            description="Rockchip ARM processors (RK3399, OP1, RK3588)",
            manufacturer="Rockchip",
            common_boards=["ROCK Pi 4", "ROCK Pi 4B+", "ROCK Pi 5", "NanoPi M4"],
        ),
        SOCFamily.BROADCOM: SOCRegistryEntry(
            family=SOCFamily.BROADCOM,
            detector_class=BroadcomDetector,
            description="Broadcom ARM processors (BCM2835, BCM2711, BCM2712)",
            manufacturer="Broadcom",
            common_boards=["Raspberry Pi 1", "Raspberry Pi 4", "Raspberry Pi 5"],
        ),
        SOCFamily.ALLWINNER: SOCRegistryEntry(
            family=SOCFamily.ALLWINNER,
            detector_class=AllwinnerDetector,
            description="Allwinner ARM processors (H6, H616, H618, A64)",
            manufacturer="Allwinner",
            common_boards=["Orange Pi 3", "Orange Pi 5", "Orange Pi Zero 2", "Pine64"],
        ),
        SOCFamily.MEDIATEK: SOCRegistryEntry(
            family=SOCFamily.MEDIATEK,
            detector_class=MediaTekDetector,
            description="MediaTek ARM processors (MT8183, MT8395)",
            manufacturer="MediaTek",
            common_boards=["Kompanio boards", "AIoT platforms"],
        ),
        SOCFamily.QUALCOMM: SOCRegistryEntry(
            family=SOCFamily.QUALCOMM,
            detector_class=QualcommDetector,
            description="Qualcomm ARM processors (QCS605)",
            manufacturer="Qualcomm",
            common_boards=["Qualcomm development boards", "IoT platforms"],
        ),
    }

    @classmethod
    def get_all_families(cls) -> List[SOCFamily]:
        """Get all registered SOC families"""
        return list(cls.REGISTERED_FAMILIES.keys())

    @classmethod
    def get_detector_class(cls, family: SOCFamily) -> Type[SOCDetector]:
        """Get detector class for a SOC family"""
        entry = cls.REGISTERED_FAMILIES.get(family)
        if entry:
            return entry.detector_class
        raise ValueError(f"Unknown SOC family: {family}")

    @classmethod
    def get_family_info(cls, family: SOCFamily) -> SOCRegistryEntry:
        """Get information about a SOC family"""
        entry = cls.REGISTERED_FAMILIES.get(family)
        if entry:
            return entry
        raise ValueError(f"Unknown SOC family: {family}")

    @classmethod
    def register_family(cls, entry: SOCRegistryEntry) -> None:
        """Register a new SOC family"""
        cls.REGISTERED_FAMILIES[entry.family] = entry

    @classmethod
    def create_all_detectors(cls) -> List[SOCDetector]:
        """Create instances of all registered detectors"""
        detectors = []
        for entry in cls.REGISTERED_FAMILIES.values():
            try:
                detector = entry.detector_class()
                detectors.append(detector)
            except Exception as e:
                print(
                    f"Warning: Failed to create detector for {entry.family.value}: {e}"
                )
        return detectors

    @classmethod
    def get_supported_boards(cls) -> Dict[str, List[str]]:
        """Get all supported boards by family"""
        boards = {}
        for family, entry in cls.REGISTERED_FAMILIES.items():
            boards[family.value] = entry.common_boards
        return boards

    @classmethod
    def find_family_by_board(cls, board_name: str) -> SOCFamily:
        """Find SOC family by board name"""
        board_lower = board_name.lower()
        for family, entry in cls.REGISTERED_FAMILIES.items():
            for board in entry.common_boards:
                if board.lower() in board_lower or board_lower in board.lower():
                    return family
        return SOCFamily.UNKNOWN


# Create a singleton registry instance
soc_registry = SOCRegistry()


def register_custom_soc_family(
    family: SOCFamily,
    detector_class: Type[SOCDetector],
    description: str,
    manufacturer: str,
    common_boards: List[str],
) -> None:
    """
    Helper function to register a custom SOC family

    Usage:
        register_custom_soc_family(
            SOCFamily.CUSTOM,
            CustomDetector,
            "Custom ARM processors",
            "Custom Manufacturer",
            ["Custom Board 1", "Custom Board 2"]
        )
    """
    entry = SOCRegistryEntry(
        family=family,
        detector_class=detector_class,
        description=description,
        manufacturer=manufacturer,
        common_boards=common_boards,
    )
    soc_registry.register_family(entry)


def get_extensibility_guide() -> str:
    """
    Get a guide for extending SOC support
    """
    return """
    SOC Extensibility Guide
    ======================

    To add support for a new SOC family:

    1. Define the SOC family in SOCFamily enum (if not already present)
    2. Create a new detector class inheriting from SOCDetector
    3. Implement the required methods:
       - detect(): Detection logic
       - get_supported_socs(): List of supported SOCs
       - _build_soc_spec(): Build SOC specification
    4. Register the new family using register_custom_soc_family()

    Example:
    --------
    class CustomDetector(SOCDetector):
        def detect(self) -> Optional[SOCSpecification]:
            # Implementation here
            pass

    register_custom_soc_family(
        SOCFamily.CUSTOM,
        CustomDetector,
        "Custom SOC description",
        "Manufacturer Name",
        ["Board 1", "Board 2"]
    )

    The system will automatically include your detector in the detection process.
    """


# Export key functions for easy importing
__all__ = [
    "SOCRegistry",
    "SOCRegistryEntry",
    "soc_registry",
    "register_custom_soc_family",
    "get_extensibility_guide",
]
