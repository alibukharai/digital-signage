"""Tests for SOC (System-on-Chip) extensibility functionality.

This module tests the dynamic SOC detection, registry system, and hardware
abstraction layer that makes the digital signage system extensible across
different hardware platforms.
"""

import unittest.mock as mock
from pathlib import Path
from typing import Any, Dict

import pytest

from src.domain.configuration_factory import ConfigurationFactory
from src.domain.soc_registry import SOCRegistry

# Test imports
from src.domain.soc_specifications import (
    AllwinnerDetector,
    BroadcomDetector,
    MediaTekDetector,
    QualcommDetector,
    RockchipDetector,
    SOCDetector,
    SOCFamily,
    SOCManager,
    SOCSpecification,
)
from src.infrastructure.hardware_abstraction import (
    BroadcomHAL,
    GenericHAL,
    HALFactory,
    IHardwareAbstractionLayer,
    RockchipHAL,
)


class TestSOCDetection:
    """Test SOC detection functionality."""

    def test_rockchip_detection(self):
        """Test Rockchip SOC detection."""
        detector = RockchipDetector()

        # Test with mocked cpuinfo
        mock_cpuinfo = {
            "Hardware": "Rockchip RK3399",
            "Revision": "1.0",
            "Serial": "000000000000",
        }

        with mock.patch(
            "src.domain.soc_specifications.RockchipDetector._get_cpuinfo",
            return_value=mock_cpuinfo,
        ):
            result = detector.detect()

        assert result is not None
        assert result.family == SOCFamily.ROCKCHIP
        assert result.model == "RK3399"
        assert result.manufacturer == "Rockchip"

    def test_unknown_soc_fallback(self):
        """Test fallback to generic SOC when detection fails."""
        manager = SOCManager()

        # Mock all detectors to return None
        with mock.patch.object(
            RockchipDetector, "detect", return_value=None
        ), mock.patch.object(
            BroadcomDetector, "detect", return_value=None
        ), mock.patch.object(
            AllwinnerDetector, "detect", return_value=None
        ), mock.patch.object(
            MediaTekDetector, "detect", return_value=None
        ), mock.patch.object(
            QualcommDetector, "detect", return_value=None
        ):
            result = manager.detect_soc()

        assert result is not None
        assert result.family == SOCFamily.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
