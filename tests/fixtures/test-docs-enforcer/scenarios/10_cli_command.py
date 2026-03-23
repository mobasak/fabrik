"""Scenario 10: New CLI argument."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="MyApp CLI")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    args = parser.parse_args()
    print(f"Format: {args.format}, Output: {args.output_dir}, Dry: {args.dry_run}")
