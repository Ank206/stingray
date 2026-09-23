import sqlite3
import hashlib
import zstandard as zstd
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from .config import DB_PATH, STORE_DIR

CHUNK_SIZE = 1024 * 1024  # 1MB

def delete_file(filepath):
    """Chunks the file, deduplicates, compresses, and saves metadata."""
    path = Path(filepath).resolve()
    
    if not path.exists() or not path.is_file():
        print(f"Error: File '{filepath}' does not exist or is not a regular file.")
        return

    timestamp = datetime.now().isoformat()
    
    # Capture metadata before compression
    st = path.stat()
    permissions = st.st_mode
    last_modified = st.st_mtime
    original_size = st.st_size
    
    try:
        # Full file hasher
        full_hasher = hashlib.sha256()
        chunk_hashes = []
        
        # Read and chunk the file
        with open(path, 'rb') as f:
            while True:
                raw_chunk = f.read(CHUNK_SIZE)
                if not raw_chunk:
                    break
                    
                full_hasher.update(raw_chunk)
                
                # Hash the chunk
                chunk_hash = hashlib.sha256(raw_chunk).hexdigest()
                chunk_hashes.append(chunk_hash)
                
                # Deduplication check
                dest_path = STORE_DIR / chunk_hash
                if not dest_path.exists():
                    # Compress and write atomically
                    tmp_path = dest_path.with_suffix('.tmp')
                    cctx = zstd.ZstdCompressor()
                    compressed_chunk = cctx.compress(raw_chunk)
                    
                    with open(tmp_path, 'wb') as tmp_f:
                        tmp_f.write(compressed_chunk)
                    
                    # Atomic rename
                    tmp_path.rename(dest_path)
                    
        full_file_hash = full_hasher.hexdigest()
        
        # Save to database
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Insert file record
            cursor.execute(
                "INSERT INTO deleted_files (original_path, original_size, permissions, last_modified, deleted_at, full_file_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (str(path), original_size, permissions, last_modified, timestamp, full_file_hash)
            )
            file_id = cursor.lastrowid
            
            # Insert chunk records
            for order, chash in enumerate(chunk_hashes):
                cursor.execute(
                    "INSERT INTO file_chunks (file_id, chunk_hash, chunk_order) VALUES (?, ?, ?)",
                    (file_id, chash, order)
                )
                
            conn.commit()
            
        path.unlink()
        print(f"Safely deleted: {path}")
        
    except Exception as e:
        print(f"Failed to delete '{filepath}': {e}")

def restore_file(filepath):
    """Reconstructs a file, verifies checksum, and Auto-GCs the vault."""
    path = Path(filepath).resolve()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Fetch file metadata
        cursor.execute(
            "SELECT id, permissions, last_modified, original_size, full_file_hash FROM deleted_files WHERE original_path = ? ORDER BY deleted_at DESC LIMIT 1",
            (str(path),)
        )
        row = cursor.fetchone()
        
        if not row:
            print(f"Error: No record found for '{path}'.")
            return
            
        file_id, permissions, last_modified, expected_size, expected_hash = row
        
        # Fetch chunks
        cursor.execute(
            "SELECT chunk_hash FROM file_chunks WHERE file_id = ? ORDER BY chunk_order ASC",
            (file_id,)
        )
        chunk_rows = cursor.fetchall()
        
        try:
            full_hasher = hashlib.sha256()
            dctx = zstd.ZstdDecompressor()
            
            with open(path, 'wb') as f_out:
                for (chunk_hash,) in chunk_rows:
                    chunk_path = STORE_DIR / chunk_hash
                    
                    if not chunk_path.exists():
                        raise FileNotFoundError(f"Missing chunk {chunk_hash}")
                        
                    with open(chunk_path, 'rb') as f_in:
                        compressed_data = f_in.read()
                        raw_chunk = dctx.decompress(compressed_data)
                        
                        f_out.write(raw_chunk)
                        full_hasher.update(raw_chunk)
            
            # Verify size and hash
            actual_size = path.stat().st_size
            actual_hash = full_hasher.hexdigest()
            
            if actual_size != expected_size or actual_hash != expected_hash:
                print(f"CRITICAL ERROR: Data corruption detected in '{path}'. Hash mismatch! Aborting restore.")
                path.unlink()  # Delete the corrupted reconstructed file
                return
            
            # Restore metadata
            path.chmod(permissions)
            os.utime(path, (last_modified, last_modified)) 
            
            print(f"Successfully restored and verified: {path}")
            
            # AUTO-GC: Remove from database
            cursor.execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM deleted_files WHERE id = ?", (file_id,))
            conn.commit()
            
            # AUTO-GC: Clean up orphaned chunks specifically for this file
            deleted_chunks = 0
            for (chunk_hash,) in chunk_rows:
                cursor.execute("SELECT 1 FROM file_chunks WHERE chunk_hash = ? LIMIT 1", (chunk_hash,))
                if not cursor.fetchone():
                    # No other file needs this chunk
                    chunk_path = STORE_DIR / chunk_hash
                    if chunk_path.exists():
                        chunk_path.unlink()
                        deleted_chunks += 1
                        
            print(f"Auto-GC: Reclaimed {deleted_chunks} orphaned chunks from the vault.")
            
        except Exception as e:
            print(f"Failed to restore '{filepath}': {e}")
            if path.exists():
                path.unlink() # Cleanup partial restore on error

def restore_all_files():
    """Restores all files currently in the vault."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT original_path FROM deleted_files")
        rows = cursor.fetchall()
        
    if not rows:
        print("Vault is empty. Nothing to restore.")
        return
        
    for (path,) in rows:
        restore_file(path)
        
def garbage_collect(days):
    """Prunes DB records older than N days and sweeps physical orphans safely."""
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Phase 1: Database Pruning
        cursor.execute("SELECT id FROM deleted_files WHERE deleted_at < ?", (cutoff_iso,))
        expired_files = cursor.fetchall()
        
        if expired_files:
            expired_ids = [row[0] for row in expired_files]
            placeholders = ','.join('?' * len(expired_ids))
            
            cursor.execute(f"DELETE FROM file_chunks WHERE file_id IN ({placeholders})", expired_ids)
            cursor.execute(f"DELETE FROM deleted_files WHERE id IN ({placeholders})", expired_ids)
            conn.commit()
            print(f"GC: Pruned {len(expired_ids)} old files from the database.")
        else:
            print(f"GC: No files older than {days} days to prune.")
            
        # Phase 2: High-Speed Orphan Sweeping
        print("GC: Sweeping for orphaned physical chunks...")
        cursor.execute("SELECT DISTINCT chunk_hash FROM file_chunks")
        active_hashes = {row[0] for row in cursor.fetchall()}
        
        now = time.time()
        one_hour_sec = 3600
        reclaimed_space = 0
        deleted_count = 0
        
        for entry in os.scandir(STORE_DIR):
            if entry.is_file() and not entry.name.endswith('.tmp'):
                # Is it an active hash?
                if entry.name not in active_hashes:
                    # Is it older than 1 hour? (Concurrency Safety)
                    if (now - entry.stat().st_mtime) > one_hour_sec:
                        reclaimed_space += entry.stat().st_size
                        os.unlink(entry.path)
                        deleted_count += 1
                        
        print(f"GC: Swept and deleted {deleted_count} orphaned chunks.")
        print(f"GC: Reclaimed {reclaimed_space / (1024*1024):.2f} MB of physical space.")


def list_files():
    """Lists all files currently stored in the vault."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT original_path, deleted_at, original_size FROM deleted_files ORDER BY deleted_at DESC")
        rows = cursor.fetchall()
        
        if not rows:
            print("The vault is empty.")
            return
            
        print(f"{'Deletion Time':<25} | {'Size (bytes)':<15} | {'Original Path'}")
        print("-" * 100)
        for row in rows:
            print(f"{row[1]:<25} | {row[2]:<15} | {row[0]}")

def stats():
    """Calculates space savings and prints a report."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. Logical size
        cursor.execute("SELECT SUM(original_size) FROM deleted_files")
        row = cursor.fetchone()
        logical_size = row[0] if row and row[0] else 0
        
        # 2. Physical size
        physical_size = 0
        if STORE_DIR.exists():
            for entry in os.scandir(STORE_DIR):
                if entry.is_file() and not entry.name.endswith('.tmp'):
                    physical_size += entry.stat().st_size
                    
        # 3. Math
        savings_bytes = logical_size - physical_size
        savings_percent = (savings_bytes / logical_size * 100) if logical_size > 0 else 0
        ratio = (logical_size / physical_size) if physical_size > 0 else 0
        
        print("=== sdel Storage Statistics ===")
        print(f"Logical Data Size : {logical_size / (1024*1024):>10.2f} MB")
        print(f"Physical Vault Size: {physical_size / (1024*1024):>10.2f} MB")
        print("-" * 31)
        if logical_size > 0:
            print(f"Total Space Saved : {savings_bytes / (1024*1024):>10.2f} MB ({savings_percent:.1f}%)")
            print(f"Compression Ratio : {ratio:>10.2f}x")
        else:
            print("Vault is empty. Delete some files to see stats!")
