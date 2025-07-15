#!/usr/bin/env python3
"""
Setup script for Rock Pi 3399 Provisioning System
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    with open(readme_file, 'r', encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = "Production-grade network provisioning system for Rock Pi 3399"

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f 
                       if line.strip() and not line.startswith('#')]
else:
    requirements = []

setup(
    name="rock-pi-provisioning",
    version="2.0.0",
    author="Rock Pi Development Team",
    author_email="dev@rockpi.org",
    description="Production-grade network provisioning system for Rock Pi 3399",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rockpi/provisioning-system",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0",
            "flake8>=4.0",
            "pylint>=2.12",
            "safety>=2.0",
            "pip-tools>=6.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "rock-provision=src.main:main",
            "rock-diagnose=src.utils.diagnostics:main",
            "rock-status=src.utils.system_status:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml"],
    },
)
