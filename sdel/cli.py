import sys
import argparse
from .db import init_db
from .core import delete_file, restore_file, list_files

def main():
    parser = argparse.ArgumentParser(description="sdel: A safer alternative to rm")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    restore_parser = subparsers.add_parser("restore", help="Restore a deleted file")
    restore_parser.add_argument("file", help="Path to the file to restore")
    
    list_parser = subparsers.add_parser("list", help="List all deleted files in the vault")
    
    if len(sys.argv) > 1 and sys.argv[1] not in ("restore", "list", "-h", "--help"):
        target_file = sys.argv[1]
        init_db()
        delete_file(target_file)
        return

    args = parser.parse_args()
    
    init_db()
    
    if args.command == "restore":
        restore_file(args.file)
    elif args.command == "list":
        list_files()
    else:
        parser.print_help()
