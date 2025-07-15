#!/usr/bin/env python3
"""
Rock Pi 3399 Provisioning System - Test Runner

This script provides comprehensive test execution for the Rock Pi 3399 
provisioning system with scenario-based organization and detailed reporting.

Usage:
    python run_tests.py [options]
    
Options:
    --category <category>  Run tests for specific category
    --scenario <scenario>  Run specific scenario test
    --integration         Run integration tests only
    --critical           Run critical tests only
    --performance        Run performance tests only
    --coverage           Generate coverage report
    --report             Generate detailed test report
    --verbose            Verbose output
    --help               Show this help message

Test Categories:
    - first_time_setup: F1-F3 scenarios
    - normal_operation: N1-N2 scenarios  
    - factory_reset: R1-R2 scenarios
    - error_recovery: E1-E2 scenarios
    - security_validation: S1-S2 scenarios
    - all: Run all test categories
"""

import sys
import os
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


class TestRunner:
    """
    Comprehensive test runner for Rock Pi 3399 provisioning system.
    """
    
    def __init__(self):
        self.test_root = Path(__file__).parent / "tests"
        self.categories = {
            "first_time_setup": {
                "path": "first_time_setup",
                "description": "First-Time Setup Core Tests (F1-F3)",
                "scenarios": ["F1", "F2", "F3"],
                "coverage_target": 93.0
            },
            "normal_operation": {
                "path": "normal_operation", 
                "description": "Normal Operation Tests (N1-N2)",
                "scenarios": ["N1", "N2"],
                "coverage_target": 97.5
            },
            "factory_reset": {
                "path": "factory_reset",
                "description": "Factory Reset Tests (R1-R2)", 
                "scenarios": ["R1", "R2"],
                "coverage_target": 82.5
            },
            "error_recovery": {
                "path": "error_recovery",
                "description": "Error Recovery Tests (E1-E2)",
                "scenarios": ["E1", "E2"],
                "coverage_target": 72.5
            },
            "security_validation": {
                "path": "security_validation",
                "description": "Security Validation Tests (S1-S2)",
                "scenarios": ["S1", "S2"], 
                "coverage_target": 80.0
            }
        }
        
        self.scenario_mapping = {
            "F1": "Clean boot + valid provisioning",
            "F2": "Invalid credential handling",
            "F3": "Owner PIN registration",
            "N1": "Auto-reconnect on reboot",
            "N2": "Network change handling", 
            "R1": "Hardware button reset",
            "R2": "Reset during active session",
            "E1": "BLE recovery",
            "E2": "Display failure",
            "S1": "PIN lockout",
            "S2": "Encrypted credentials"
        }
    
    def run_category_tests(self, category: str, verbose: bool = False, coverage: bool = False) -> Dict[str, Any]:
        """Run tests for a specific category."""
        if category not in self.categories:
            raise ValueError(f"Unknown category: {category}")
        
        category_info = self.categories[category]
        test_path = self.test_root / category_info["path"]
        
        if not test_path.exists():
            raise FileNotFoundError(f"Test directory not found: {test_path}")
        
        print(f"\n🧪 Running {category_info['description']}")
        print(f"📁 Test path: {test_path}")
        print(f"🎯 Target coverage: {category_info['coverage_target']}%")
        print(f"📋 Scenarios: {', '.join(category_info['scenarios'])}")
        print("-" * 60)
        
        # Build pytest command
        cmd = ["python", "-m", "pytest", str(test_path)]
        
        if verbose:
            cmd.extend(["-v", "--tb=long"])
        else:
            cmd.extend(["-q", "--tb=short"])
        
        if coverage:
            cmd.extend([
                f"--cov=src",
                f"--cov-report=term-missing",
                f"--cov-report=html:htmlcov/{category}",
            ])
        
        # Add markers
        cmd.extend(["-m", f"{category}"])
        
        # Run tests
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "category": category,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "target_coverage": category_info["coverage_target"]
            }
            
        except Exception as e:
            return {
                "category": category,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "target_coverage": category_info["coverage_target"]
            }
    
    def run_scenario_test(self, scenario: str, verbose: bool = False) -> Dict[str, Any]:
        """Run tests for a specific scenario."""
        if scenario not in self.scenario_mapping:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        # Find which category contains this scenario
        category = None
        for cat_name, cat_info in self.categories.items():
            if scenario in cat_info["scenarios"]:
                category = cat_name
                break
        
        if not category:
            raise ValueError(f"Category not found for scenario: {scenario}")
        
        print(f"\n🎯 Running Scenario {scenario}: {self.scenario_mapping[scenario]}")
        print(f"📂 Category: {self.categories[category]['description']}")
        print("-" * 60)
        
        test_path = self.test_root / self.categories[category]["path"]
        
        # Build pytest command for specific scenario
        cmd = ["python", "-m", "pytest", str(test_path), "-k", scenario.lower()]
        
        if verbose:
            cmd.extend(["-v", "--tb=long"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "scenario": scenario,
                "description": self.scenario_mapping[scenario],
                "category": category,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except Exception as e:
            return {
                "scenario": scenario,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def run_all_tests(self, verbose: bool = False, coverage: bool = False) -> Dict[str, Any]:
        """Run all test categories."""
        print("🚀 Running Complete Test Suite for Rock Pi 3399 Provisioning System")
        print("=" * 80)
        
        results = {}
        total_success = True
        
        for category in self.categories.keys():
            result = self.run_category_tests(category, verbose, coverage)
            results[category] = result
            
            if not result["success"]:
                total_success = False
            
            # Print immediate result
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {category}")
        
        results["overall_success"] = total_success
        return results
    
    def run_integration_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run integration tests that span multiple categories."""
        print("\n🔗 Running Integration Tests")
        print("-" * 40)
        
        cmd = ["python", "-m", "pytest", str(self.test_root), "-m", "integration"]
        
        if verbose:
            cmd.extend(["-v", "--tb=long"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "test_type": "integration",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except Exception as e:
            return {
                "test_type": "integration",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def run_critical_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run only critical tests that must pass."""
        print("\n⚠️  Running Critical Tests")
        print("-" * 30)
        
        cmd = ["python", "-m", "pytest", str(self.test_root), "-m", "critical"]
        
        if verbose:
            cmd.extend(["-v", "--tb=long"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "test_type": "critical",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except Exception as e:
            return {
                "test_type": "critical",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def run_performance_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """Run performance and timing tests."""
        print("\n⏱️  Running Performance Tests")
        print("-" * 35)
        
        cmd = ["python", "-m", "pytest", str(self.test_root), "-m", "performance"]
        
        if verbose:
            cmd.extend(["-v", "--tb=long"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "test_type": "performance",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except Exception as e:
            return {
                "test_type": "performance",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def generate_report(self, results: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """Generate detailed test report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""
# Rock Pi 3399 Provisioning System - Test Report

**Generated:** {timestamp}  
**Test Runner:** Rock Pi Test Suite v1.0  
**System Under Test:** Rock Pi 3399 Provisioning System  

## Executive Summary

"""
        
        if "overall_success" in results:
            total_categories = len([k for k in results.keys() if k != "overall_success"])
            passed_categories = len([k for k, v in results.items() 
                                   if k != "overall_success" and v.get("success", False)])
            
            report += f"- **Total Categories:** {total_categories}\n"
            report += f"- **Passed Categories:** {passed_categories}\n"
            report += f"- **Failed Categories:** {total_categories - passed_categories}\n"
            report += f"- **Overall Success:** {'✅ YES' if results['overall_success'] else '❌ NO'}\n\n"
        
        report += "## Test Results by Category\n\n"
        
        for category, info in self.categories.items():
            if category in results:
                result = results[category]
                status = "✅ PASS" if result["success"] else "❌ FAIL"
                target = result.get("target_coverage", 0)
                
                report += f"### {info['description']}\n"
                report += f"- **Status:** {status}\n"
                report += f"- **Target Coverage:** {target}%\n"
                report += f"- **Scenarios:** {', '.join(info['scenarios'])}\n"
                
                if not result["success"] and result.get("stderr"):
                    report += f"- **Error:** {result['stderr'][:200]}...\n"
                
                report += "\n"
        
        report += "## Scenario Coverage Analysis\n\n"
        
        for scenario, description in self.scenario_mapping.items():
            report += f"- **{scenario}:** {description}\n"
        
        report += "\n## Recommendations\n\n"
        
        if results.get("overall_success", False):
            report += "- ✅ All test categories passed successfully\n"
            report += "- 🎯 System is ready for deployment\n"
            report += "- 🔍 Consider adding additional edge case tests\n"
        else:
            report += "- ❌ Some test categories failed\n"
            report += "- 🔧 Review and fix failing tests before deployment\n"
            report += "- 📋 Check system configuration and dependencies\n"
        
        report += "\n---\n"
        report += f"**Report generated by Rock Pi Test Runner on {timestamp}**\n"
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"📄 Report saved to: {output_file}")
        
        return report


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Rock Pi 3399 Provisioning System Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--category",
        choices=["first_time_setup", "normal_operation", "factory_reset", 
                "error_recovery", "security_validation", "all"],
        help="Run tests for specific category"
    )
    
    parser.add_argument(
        "--scenario",
        choices=["F1", "F2", "F3", "N1", "N2", "R1", "R2", "E1", "E2", "S1", "S2"],
        help="Run specific scenario test"
    )
    
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests only"
    )
    
    parser.add_argument(
        "--critical",
        action="store_true",
        help="Run critical tests only"
    )
    
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Run performance tests only"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--report",
        metavar="FILE",
        help="Generate detailed test report to file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    results = {}
    
    try:
        if args.scenario:
            results = runner.run_scenario_test(args.scenario, args.verbose)
            
        elif args.integration:
            results = runner.run_integration_tests(args.verbose)
            
        elif args.critical:
            results = runner.run_critical_tests(args.verbose)
            
        elif args.performance:
            results = runner.run_performance_tests(args.verbose)
            
        elif args.category:
            if args.category == "all":
                results = runner.run_all_tests(args.verbose, args.coverage)
            else:
                results = {args.category: runner.run_category_tests(args.category, args.verbose, args.coverage)}
                
        else:
            # Default: run all tests
            results = runner.run_all_tests(args.verbose, args.coverage)
        
        # Generate report if requested
        if args.report:
            runner.generate_report(results, args.report)
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 TEST EXECUTION SUMMARY")
        print("=" * 80)
        
        if isinstance(results, dict) and "overall_success" in results:
            overall_status = "✅ SUCCESS" if results["overall_success"] else "❌ FAILURE"
            print(f"Overall Result: {overall_status}")
            
            for category, result in results.items():
                if category != "overall_success":
                    status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
                    print(f"  {category}: {status}")
        else:
            status = "✅ PASS" if results.get("success", False) else "❌ FAIL"
            test_type = results.get("test_type", results.get("category", results.get("scenario", "unknown")))
            print(f"{test_type}: {status}")
        
        # Exit with appropriate code
        if isinstance(results, dict) and "overall_success" in results:
            sys.exit(0 if results["overall_success"] else 1)
        else:
            sys.exit(0 if results.get("success", False) else 1)
            
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
