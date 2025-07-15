#!/usr/bin/env python3
"""
Setup script for Rock Pi 3399 Provisioning System

This setup.py is kept for compatibility but the project now uses pyproject.toml
for modern Python packaging. To install:

    pip install -e .              # Production dependencies
    pip install -e ".[dev]"       # Include development dependencies
"""

from setuptools import setup

# All configuration is now in pyproject.toml
# This setup.py exists for compatibility with tools that don't support PEP 518
setup()
