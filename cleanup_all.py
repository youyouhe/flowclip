#!/usr/bin/env python3
"""
Non-interactive cleanup script for YouTube Slicer
Run all cleanup tasks automatically
"""

import sys
import subprocess
import os
from pathlib import Path

def run_cleanup():
    """Run all cleanup tasks automatically"""
    
    print("🧹 Running automatic cleanup...")
    print("=" * 40)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Import and run cleanup functions
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fix_script", "fix_duplicate_videos.py")
        fix_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_module)
        
        # Run all cleanup functions
        print("🔧 Running duplicate video fix...")
        fix_module.fix_duplicate_videos()
        
        print("\n🚨 Cleaning up stuck downloads...")
        fix_module.cleanup_stuck_videos()
        
        print("\n🔄 Resetting stuck processing status...")
        fix_module.reset_processing_status()
        
        print("\n🎉 All cleanup tasks completed successfully!")
        
    except Exception as e:
        print(f"❌ Error running cleanup: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = run_cleanup()
    sys.exit(0 if success else 1)