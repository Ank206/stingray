#!/bin/bash

echo "=== 1. Wiping old Step 2 Database ==="
rm -rf ~/.sdel

echo "=== 2. Activating venv ==="
source venv/bin/activate

echo "=== 3. Creating a 5MB test file ==="
dd if=/dev/zero of=fileA.bin bs=1M count=5

echo "=== 4. Making an exact copy ==="
cp fileA.bin fileB.bin

echo "=== 5. Deleting fileA.bin ==="
python3 sdel.py fileA.bin

echo "=== 6. Deleting fileB.bin ==="
python3 sdel.py fileB.bin

echo "=== 7. Listing Database Records ==="
python3 sdel.py list

echo "=== 8. Checking physical vault size (Deduplication check!) ==="
echo "If dedup worked, the chunk folder should only hold ~5MB of raw data (heavily compressed to KB) instead of 10MB."
du -sh ~/.sdel/chunks/
ls -l ~/.sdel/chunks/

echo "=== 9. Restoring both files ==="
python3 sdel.py restore fileA.bin
python3 sdel.py restore fileB.bin

echo "=== 10. Confirming files exist ==="
ls -lh fileA.bin fileB.bin
