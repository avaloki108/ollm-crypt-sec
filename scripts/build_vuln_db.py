#!/usr/bin/env python3
"""Build vulnerability embedding database for audit engine.

This script generates embeddings for known vulnerability patterns using
SmartBERT and saves them to a database for similarity matching during audits.
"""

import argparse
import pathlib
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from mcp_client_for_ollama.agents.audit_engine import build_vuln_db, VULN_DB_PATH


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build vulnerability embedding database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build with default settings
  python build_vuln_db.py
  
  # Use custom SmartBERT URL
  python build_vuln_db.py --url http://localhost:9900/embed
  
  # Custom output path
  python build_vuln_db.py --output ~/my_vuln_db.json
        """
    )
    
    parser.add_argument(
        "--url",
        default="http://localhost:9900/embed",
        help="SmartBERT API endpoint URL (default: http://localhost:9900/embed)"
    )
    
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=VULN_DB_PATH,
        help=f"Output path for database (default: {VULN_DB_PATH})"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if SmartBERT service is available before building"
    )
    
    args = parser.parse_args()
    
    # Check service availability if requested
    if args.check:
        try:
            import requests
            response = requests.get(args.url.replace("/embed", "/health"), timeout=5)
            if response.status_code != 200:
                print(f"⚠️  Warning: SmartBERT service health check returned {response.status_code}")
                print("  Continuing anyway...")
        except Exception as e:
            print(f"⚠️  Warning: Could not check SmartBERT service: {e}")
            print("  Continuing anyway...")
    
    # Build database
    print(f"Building vulnerability database...")
    print(f"  SmartBERT URL: {args.url}")
    print(f"  Output path: {args.output}")
    print()
    
    success = build_vuln_db(args.url, args.output)
    
    if success:
        print(f"\n✅ Successfully built vulnerability database")
        print(f"   Database contains embeddings for known vulnerability patterns")
        print(f"   Use this database during audits for similarity matching")
        return 0
    else:
        print(f"\n❌ Failed to build vulnerability database")
        print(f"   Check that SmartBERT service is running at {args.url}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

