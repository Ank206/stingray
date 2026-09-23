# sdel (Safe Delete)

A systems-level, robust alternative to the Unix `rm` command. 

Instead of permanently wiping files, `sdel` intercepts the deletion and safely stores the file in a hidden vault (`~/.sdel/`). But it doesn't just copy the file—it leverages **Content Addressed Storage (CAS)**, chunking, and compression to heavily reduce disk usage, much like Git or Restic.

## Features
- **Deduplication:** Files are split into 1MB chunks and hashed. If you delete 5 copies of the same 1GB movie, it only takes up 1GB of space in the vault. 
- **Zstandard Compression:** Every unique chunk is individually compressed for blazing-fast read/write speeds and massive storage savings on text/code.
- **Atomic & Safe:** Data is strictly verified using SHA-256 hashes during restoration. Atomic `.tmp` writes prevent silent data corruption if your system crashes mid-delete.
- **Smart Garbage Collection:** `sdel` includes an $O(1)$ memory Mark-and-Sweep garbage collector that automatically reclaims physical disk space when deleted files expire, fully protected against race conditions.
- **Analytics:** Run `sdel stats` at any time to see exactly how much physical disk space the deduplication engine is saving you!

## Usage

### 1. Delete a file (or multiple files)
```bash
python3 sdel.py my_file.txt
python3 sdel.py *.log
```

### 2. View the Vault
```bash
python3 sdel.py list
```

### 3. Check Storage Savings
```bash
python3 sdel.py stats
```
*Outputs Logical Data Size vs Physical Vault Size and your compression ratio.*

### 4. Restore files
```bash
python3 sdel.py restore my_file.txt
python3 sdel.py restore --allfiles
```
*Note: Restoring a file will automatically verify its integrity, place it back in your directory, and sweep the vault of any orphaned chunks to keep your storage clean.*

### 5. Garbage Collection
By default, files older than 120 days are considered expired. To sweep the database and reclaim physical disk space:
```bash
python3 sdel.py gc
```
*You can customize the expiry window with `sdel gc --days 30`.*

## Installation & Setup
`sdel` relies on SQLite3 and Python 3. It requires the `zstandard` package:
```bash
python3 -m venv venv
source venv/bin/activate
pip install zstandard
```
