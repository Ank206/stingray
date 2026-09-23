#!/bin/bash

echo "=== 1. Activating venv ==="
source venv/bin/activate

echo "=== 2. Creating a test file ==="
dd if=/dev/urandom of=gc_test.bin bs=1M count=3

echo "=== 3. Deleting it to the vault ==="
python3 sdel.py gc_test.bin

echo "=== 4. Running GC for 0 days ==="
python3 sdel.py gc --days 0

echo "=== 5. Listing Vault (Should be empty!) ==="
python3 sdel.py list

echo "=== 6. Checking physical chunk folder (Should have NO orphaned chunks older than 1 hour) ==="
ls -lh ~/.sdel/chunks/
