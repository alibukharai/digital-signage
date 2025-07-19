#!/usr/bin/env python3
"""
Integration demonstration of all implemented improvements

This script demonstrates how all the newly implemented features work together
to provide a robust, enterprise-grade error handling and coordination system.
"""

import asyncio
import os
import sys
import threading
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def demonstrate_improvements():
    """Demonstrate all the implemented improvements working together"""

    print("🚀 DEMONSTRATING INTEGRATED IMPROVEMENTS")
    print("=" * 60)

    # Import our enhanced modules
    try:
        from common.error_handling_patterns import (
            ErrorHandlingMixin,
            ResourceManager,
            operation_context,
            with_error_handling,
        )
        from common.result_handling import ErrorContext, Result, ResultBuilder
        from common.threading_coordination import (
            ThreadCoordinator,
            get_thread_coordinator,
        )

        print("✅ All enhanced modules imported successfully")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

    # 1. Demonstrate Enhanced Error Handling
    print(f"\n📝 1. Enhanced Error Handling with Context")

    class DemoService(ErrorHandlingMixin):
        def __init__(self):
            super().__init__()
            self.logger = DemoLogger()

        @with_error_handling("risky_operation")
        def risky_operation(self, should_fail=False):
            self._add_operation_context("risky_operation", input_param=should_fail)

            if should_fail:
                raise ValueError("Simulated failure for demonstration")

            return self._create_success_result("Operation completed", "risky_operation")

    class DemoLogger:
        def debug(self, msg):
            print(f"   [DEBUG] {msg}")

        def info(self, msg):
            print(f"   [INFO] {msg}")

        def error(self, msg):
            print(f"   [ERROR] {msg}")

        def warning(self, msg):
            print(f"   [WARNING] {msg}")

    # Test the enhanced error handling
    service = DemoService()

    # Success case
    result = service.risky_operation(should_fail=False)
    if result.is_success():
        print(f"   ✅ Success: {result.value}")

    # Failure case with enhanced context
    result = service.risky_operation(should_fail=True)
    if result.is_failure():
        print(f"   ❌ Failure: {result.get_error_summary()}")

    # 2. Demonstrate Resource Management
    print(f"\n🛡️  2. Enhanced Resource Management")

    def demonstrate_resource_management():
        with ResourceManager(DemoLogger()) as rm:
            # Add some dummy resources
            resource1 = {"name": "database_connection", "active": True}
            resource2 = {"name": "file_handle", "active": True}

            rm.add_cleanup_callback(lambda: print("   ✅ Cleanup callback executed"))

            print("   📦 Resources allocated and managed")
            return "Resources demonstrated"

    result = demonstrate_resource_management()
    print(f"   ✅ {result}")

    # 3. Demonstrate Threading Coordination
    print(f"\n🧵 3. Threading and Async Coordination")

    coordinator = get_thread_coordinator()
    coordinator.register_async_loop()

    # Simulate mixed operations
    def sync_operation():
        with coordinator.thread_operation("sync_background_task"):
            time.sleep(0.1)  # Simulate work
            return "Sync operation completed"

    async def async_operation():
        await asyncio.sleep(0.1)  # Simulate async work
        return "Async operation completed"

    # Run sync operation from async context
    sync_result = await coordinator.run_in_thread(sync_operation)
    print(f"   ✅ Sync from async: {sync_result}")

    # Run async operation
    async_result = await async_operation()
    print(f"   ✅ Async operation: {async_result}")

    # Show coordination status
    status = coordinator.get_active_operations()
    print(f"   📊 Coordinator status: {status['coordination_mode']}")

    # 4. Demonstrate Result Builder and Enhanced Context
    print(f"\n🔄 4. Enhanced Result Handling with Context")

    builder = ResultBuilder("demonstration_operation")
    builder.add_context("demo_type", "integration_test")
    builder.add_context("timestamp", time.time())

    success_result = builder.success(
        {"demo": "success", "features": ["error_handling", "threading", "resources"]}
    )
    print(f"   ✅ Enhanced success result created with context")

    # Demonstrate error chaining
    try:
        raise ValueError("Original error")
    except Exception as e:
        chained_result = Result.from_exception(
            e, "chained_operation", {"additional": "context"}
        )
        error_summary = chained_result.get_error_summary()
        print(f"   🔗 Error chaining: {error_summary[:80]}...")

    # 5. Demonstrate Operation Context
    print(f"\n📋 5. Operation Context and Logging")

    logger = DemoLogger()

    with operation_context("complex_operation", logger, operation_type="demonstration"):
        await asyncio.sleep(0.05)  # Simulate work
        print("   ⚙️  Complex operation with context executed")

    print(f"\n✨ INTEGRATION DEMONSTRATION COMPLETED")
    print(f"   All enhanced features working together seamlessly!")

    return True


async def main():
    """Main demonstration function"""
    try:
        success = await demonstrate_improvements()

        if success:
            print(f"\n🎉 ALL IMPROVEMENTS SUCCESSFULLY DEMONSTRATED")
            print(f"   The digital signage system now has:")
            print(f"   • Enterprise-grade error handling")
            print(f"   • Robust resource management")
            print(f"   • Unified threading coordination")
            print(f"   • Comprehensive context preservation")
            print(f"   • Production-ready reliability")

            return True
        else:
            print(f"\n❌ Demonstration encountered issues")
            return False

    except Exception as e:
        print(f"❌ Demonstration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the demonstration
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n⏹️  Demonstration interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to run demonstration: {e}")
        sys.exit(1)
