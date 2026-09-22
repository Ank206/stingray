import sqlite3
import hashlib
import zstandard as zstd
import os
from pathlib import Path
from datetime import datetime
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
    """Reconstructs a file from its chunks and verifies checksum."""
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
                print(f"CRITICAL ERROR: Data corruption detected in '{path}'. Hash mismatch!")
                # Keep the file but warn the user
            
            # Restore metadata
            path.chmod(permissions)
            os.utime(path, (last_modified, last_modified)) 
            
            print(f"Successfully restored and verified: {path}")
            
        except Exception as e:
            print(f"Failed to restore '{filepath}': {e}")

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
