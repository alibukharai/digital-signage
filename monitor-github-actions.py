#!/usr/bin/env python3
"""
GitHub Actions Usage Monitor

Helps track and optimize GitHub Actions usage for free tier accounts.
Run this script to get insights into your workflow efficiency.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_workflow_files():
    """Get all workflow files in the repository."""
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        logger.error("❌ No .github/workflows directory found")
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
        logger.warning(f"⚠️ Error analyzing {workflow_file}: {e}")
        return []


def estimate_monthly_usage():
    """Estimate monthly GitHub Actions usage."""
    
    # Rough estimates based on workflow complexity
    estimates = {
        'ci-cd.yml': {'duration_minutes': 25, 'frequency_per_month': 60},
        'optimized-ci.yml': {'duration_minutes': 12, 'frequency_per_month': 60},
        'pr-validation.yml': {'duration_minutes': 8, 'frequency_per_month': 40},
        'nightly-tests.yml': {'duration_minutes': 45, 'frequency_per_month': 30},
        'monthly-tests.yml': {'duration_minutes': 45, 'frequency_per_month': 1},
        'deploy.yml': {'duration_minutes': 15, 'frequency_per_month': 20},
        'release.yml': {'duration_minutes': 20, 'frequency_per_month': 4},
    }
    
    workflows = get_workflow_files()
    total_minutes = 0
    
    logger.info("📊 GitHub Actions Usage Estimation")
    logger.info("=" * 50)
    logger.info(f"{'Workflow':<25} {'Duration':<10} {'Freq/Month':<12} {'Total':<10}")
    logger.info("-" * 50)
    
    for workflow in workflows:
        filename = workflow.name
        if filename in estimates:
            est = estimates[filename]
            monthly_minutes = est['duration_minutes'] * est['frequency_per_month']
            total_minutes += monthly_minutes
            
            logger.info(f"{filename:<25} {est['duration_minutes']:>5} min {est['frequency_per_month']:>8}/month {monthly_minutes:>7} min")

    logger.info("-" * 50)
    logger.info(f"{'TOTAL ESTIMATED':<25} {'':<10} {'':<12} {total_minutes:>7} min")
    logger.info("")
    
    # Free tier limits
    FREE_TIER_LIMIT = 2000  # minutes per month
    usage_percentage = (total_minutes / FREE_TIER_LIMIT) * 100
    
    logger.info("🎯 Free Tier Analysis:")
    logger.info(f"  • Estimated usage: {total_minutes} minutes/month")
    logger.info(f"  • Free tier limit: {FREE_TIER_LIMIT} minutes/month")
    logger.info(f"  • Usage percentage: {usage_percentage:.1f}%")
    
    if usage_percentage < 25:
        logger.info("  • Status: ✅ Excellent - Well within free limits")
    elif usage_percentage < 50:
        logger.info("  • Status: ✅ Good - Comfortable usage")
    elif usage_percentage < 80:
        logger.warning("  • Status: ⚠️ Caution - Monitor usage closely")
    else:
        logger.error("  • Status: ❌ Warning - May exceed free limits")
    
    return total_minutes, usage_percentage


def suggest_optimizations():
    """Suggest workflow optimizations."""
    workflows = get_workflow_files()
    heavy_workflows = [w for w in workflows if 'nightly' in w.name.lower() or 'full' in w.name.lower()]
    
    logger.info("\n💡 Optimization Suggestions:")
    logger.info("-" * 30)
    
    # Check for heavy workflows
    if heavy_workflows:
        logger.warning("🚨 Heavy workflows detected:")
        for workflow in heavy_workflows:
            logger.warning(f"  • {workflow.name} - Consider using optimized alternatives")
        logger.info("")
    
    logger.info("✅ Recommended optimizations:")
    logger.info("  1. Use 'optimized-ci.yml' instead of 'ci-cd.yml'")
    logger.info("  2. Replace 'nightly-tests.yml' with 'monthly-tests.yml'")
    logger.info("  3. Set up Rock Pi 3399 as self-hosted runner")
    logger.info("  4. Use draft PRs while developing")
    logger.info("  5. Enable path-based workflow filtering")
    logger.info("  6. Use workflow concurrency controls")
    logger.info("")
    
    logger.info("🎯 Advanced optimizations:")
    logger.info("  • Cache dependencies aggressively")
    logger.info("  • Use matrix builds sparingly")
    logger.info("  • Implement smart change detection")
    logger.info("  • Prefer self-hosted for hardware tests")


def check_repository_type():
    """Check if repository is public/private and on GitHub."""
    try:
        # Get remote URL
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                               capture_output=True, text=True, check=True)
        remote_url = result.stdout.strip()
        
        if 'github.com' in remote_url:
            logger.info("📦 Repository detected on GitHub")
            logger.info("💡 Note: Public repositories have unlimited GitHub Actions minutes")
            logger.info("         Private repositories have 2,000 minutes/month on free tier")
            return True
        else:
            logger.info("📦 Repository not on GitHub or different remote")
            return False
            
    except subprocess.CalledProcessError:
        logger.warning("⚠️ Could not determine repository information")
        return False


def main():
    """Main function to run the GitHub Actions monitor."""
    logger.info("🚀 GitHub Actions Usage Monitor")
    logger.info("=" * 40)
    logger.info("")
    
    check_repository_type()
    
    logger.info("")
    
    workflows = get_workflow_files()
    
    if not workflows:
        logger.error("❌ No workflow files found")
        return
    
    logger.info(f"📁 Found {len(workflows)} workflow files:")
    
    for workflow in workflows:
        triggers = analyze_workflow_triggers(workflow)
        logger.info(f"  • {workflow.name:<25} Triggers: {', '.join(triggers)}")
    logger.info("")
    
    # Estimate usage
    total_minutes, usage_percentage = estimate_monthly_usage()
    
    # Suggest optimizations
    suggest_optimizations()
    
    logger.info("\n📖 For more information:")
    logger.info("  • Setup guide: .github/SETUP_CI_CD.md")
    logger.info("  • Quick reference: .github/CI_CD_REFERENCE.md")
    logger.info("  • GitHub Actions pricing: https://github.com/pricing")


if __name__ == "__main__":
    main()
