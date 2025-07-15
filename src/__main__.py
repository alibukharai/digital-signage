#!/usr/bin/env python3
"""
Rock Pi 3399 Provisioning System Entry Point
"""

import sys
import asyncio
from .application.provisioning_orchestrator import main

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
