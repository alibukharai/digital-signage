#!/usr/bin/env python3
"""
GitHub Actions Usage Monitor

Helps track and optimize GitHub Actions usage for free tier accounts.
Run this script to get insights into your workflow efficiency.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_workflow_files():
    """Get all workflow files in the repository."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        print("❌ No .github/workflows directory found")
        return []
    
    return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))


def analyze_workflow_triggers(workflow_file):
    """Analyze triggers for a workflow file."""
    try:
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        triggers = []
        
        # Simple parsing for common triggers
        if 'push:' in content:
            triggers.append('push')
        if 'pull_request:' in content:
            triggers.append('pull_request')
        if 'schedule:' in content:
            triggers.append('schedule')
        if 'workflow_dispatch:' in content:
            triggers.append('manual')
            
        return triggers
    except Exception as e:
        print(f"⚠️ Error analyzing {workflow_file}: {e}")
        return []


def estimate_monthly_usage():
    """Estimate monthly GitHub Actions usage."""
    
    estimates = {
        'pr-validation.yml': {
            'duration_minutes': 5,
            'frequency_per_month': 20,  # 20 PRs per month
            'description': 'PR validation (fast checks)'
        },
        'optimized-ci.yml': {
            'duration_minutes': 12,
            'frequency_per_month': 25,  # 25 pushes to main/develop
            'description': 'Main CI/CD (standard tests)'
        },
        'ci-cd.yml': {
            'duration_minutes': 45,
            'frequency_per_month': 5,   # If still using the original
            'description': 'Full CI/CD (comprehensive)'
        },
        'monthly-tests.yml': {
            'duration_minutes': 90,
            'frequency_per_month': 1,   # Once per month
            'description': 'Monthly comprehensive tests'
        },
        'nightly-tests.yml': {
            'duration_minutes': 60,
            'frequency_per_month': 30,  # If still using nightly
            'description': 'Nightly tests (if enabled)'
        }
    }
    
    workflows = get_workflow_files()
    total_minutes = 0
    
    print("📊 GitHub Actions Usage Estimation")
    print("=" * 50)
    print(f"{'Workflow':<25} {'Duration':<10} {'Freq/Month':<12} {'Total':<10}")
    print("-" * 50)
    
    for workflow in workflows:
        filename = workflow.name
        if filename in estimates:
            est = estimates[filename]
            monthly_minutes = est['duration_minutes'] * est['frequency_per_month']
            total_minutes += monthly_minutes
            
            print(f"{filename:<25} {est['duration_minutes']:>5} min {est['frequency_per_month']:>8}/month {monthly_minutes:>7} min")
    
    print("-" * 50)
    print(f"{'TOTAL ESTIMATED':<25} {'':<10} {'':<12} {total_minutes:>7} min")
    print()
    
    # Free tier limits
    FREE_TIER_LIMIT = 2000  # minutes per month
    usage_percentage = (total_minutes / FREE_TIER_LIMIT) * 100
    
    print("🎯 Free Tier Analysis:")
    print(f"  • Estimated usage: {total_minutes} minutes/month")
    print(f"  • Free tier limit: {FREE_TIER_LIMIT} minutes/month")
    print(f"  • Usage percentage: {usage_percentage:.1f}%")
    
    if usage_percentage < 50:
        print("  • Status: ✅ Excellent - Well within free limits")
    elif usage_percentage < 75:
        print("  • Status: ✅ Good - Comfortable usage")
    elif usage_percentage < 90:
        print("  • Status: ⚠️ Caution - Monitor usage closely")
    else:
        print("  • Status: ❌ Warning - May exceed free limits")
    
    return total_minutes


def suggest_optimizations():
    """Suggest optimizations for GitHub Actions usage."""
    
    print("\n💡 Optimization Suggestions:")
    print("-" * 30)
    
    workflows = get_workflow_files()
    
    # Check if original heavy workflows exist
    heavy_workflows = ['ci-cd.yml', 'nightly-tests.yml']
    found_heavy = [w for w in workflows if w.name in heavy_workflows]
    
    if found_heavy:
        print("🚨 Heavy workflows detected:")
        for workflow in found_heavy:
            print(f"  • {workflow.name} - Consider using optimized alternatives")
        print()
    
    print("✅ Recommended optimizations:")
    print("  1. Use 'optimized-ci.yml' instead of 'ci-cd.yml'")
    print("  2. Replace 'nightly-tests.yml' with 'monthly-tests.yml'") 
    print("  3. Set up Rock Pi 3399 as self-hosted runner")
    print("  4. Use draft PRs while developing")
    print("  5. Enable path-based workflow filtering")
    print("  6. Use workflow concurrency controls")
    print()
    
    print("🎯 Advanced optimizations:")
    print("  • Cache dependencies aggressively")
    print("  • Use matrix builds sparingly")
    print("  • Implement smart change detection")
    print("  • Prefer self-hosted for hardware tests")


def check_repository_type():
    """Check if repository is public or private."""
    try:
        # Try to get repository info using git remote
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            check=True
        )
        
        remote_url = result.stdout.strip()
        
        if 'github.com' in remote_url:
            print("📦 Repository detected on GitHub")
            print("💡 Note: Public repositories have unlimited GitHub Actions minutes")
            print("         Private repositories have 2,000 minutes/month on free tier")
            return True
        else:
            print("📦 Repository not on GitHub or different remote")
            return False
            
    except subprocess.CalledProcessError:
        print("⚠️ Could not determine repository information")
        return False


def main():
    """Main function."""
    print("🚀 GitHub Actions Usage Monitor")
    print("=" * 40)
    print()
    
    # Check repository type
    check_repository_type()
    print()
    
    # Analyze workflows
    workflows = get_workflow_files()
    
    if not workflows:
        print("❌ No workflow files found")
        sys.exit(1)
    
    print(f"📁 Found {len(workflows)} workflow files:")
    for workflow in workflows:
        triggers = analyze_workflow_triggers(workflow)
        print(f"  • {workflow.name:<25} Triggers: {', '.join(triggers)}")
    print()
    
    # Estimate usage
    estimate_monthly_usage()
    
    # Suggest optimizations
    suggest_optimizations()
    
    print("\n📖 For more information:")
    print("  • Setup guide: .github/SETUP_CI_CD.md")
    print("  • Quick reference: .github/CI_CD_REFERENCE.md")
    print("  • GitHub Actions pricing: https://github.com/pricing")


if __name__ == "__main__":
    main()
