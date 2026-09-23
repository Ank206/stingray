import sys
import argparse
from .db import init_db
from .core import delete_file, restore_file, list_files

def main():
    parser = argparse.ArgumentParser(description="sdel: A safer alternative to rm")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    restore_parser = subparsers.add_parser("restore", help="Restore deleted file(s)")
    restore_parser.add_argument("files", nargs="*", help="Path(s) to the file(s) to restore")
    restore_parser.add_argument("--allfiles", action="store_true", help="Restore all files in the vault")
    
    list_parser = subparsers.add_parser("list", help="List all deleted files in the vault")
    
    gc_parser = subparsers.add_parser("gc", help="Garbage collect old files and orphaned chunks")
    gc_parser.add_argument("--days", type=int, default=120, help="Number of days to keep files before pruning (default: 120)")
    
    stats_parser = subparsers.add_parser("stats", help="Show storage savings and compression ratios")
    
    if len(sys.argv) > 1 and sys.argv[1] not in ("restore", "list", "gc", "stats", "-h", "--help"):
        init_db()
        import sdel.core
        for target_file in sys.argv[1:]:
            sdel.core.delete_file(target_file)
        return

    args = parser.parse_args()
    
    init_db()
    
    import sdel.core
    if args.command == "restore":
        if args.allfiles:
            sdel.core.restore_all_files()
        elif not args.files:
            print("Error: You must provide files to restore, or use --allfiles.")
        else:
            for f in args.files:
                sdel.core.restore_file(f)
    elif args.command == "list":
        sdel.core.list_files()
    elif args.command == "gc":
        sdel.core.garbage_collect(args.days)
    elif args.command == "stats":
        sdel.core.stats()
    else:
        parser.print_help()
