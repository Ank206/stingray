# `sdel` Design Decisions

This document outlines the core architectural and systems-level decisions made during the development of `sdel`, along with the rationale behind each choice.

## 1. Content-Addressed Storage (CAS) with Chunking
- **Decision:** Files are not stored as monolithic objects. They are split into 1MB chunks, hashed (SHA-256), and stored using the hash as the filename.
- **Rationale:** This enables **Deduplication**. If a user deletes 10 slightly modified versions of the same codebase, or multiple copies of the same video, `sdel` only stores the unique chunks. This saves massive amounts of disk space compared to a standard "recycle bin" approach.

## 2. 1MB Chunk Size
- **Decision:** Chunk size is set to 1MB (increased from an initial 64KB).
- **Rationale:** A 64KB chunk size creates too many physical files (e.g., a 1GB file would create ~16,000 files), choking the OS filesystem with inode exhaustion. 1MB strikes the perfect balance: it creates fewer files while still remaining granular enough to achieve excellent deduplication rates.

## 3. Zstandard (Zstd) Compression
- **Decision:** Every individual chunk is compressed using `zstandard` before being written to disk.
- **Rationale:** Zstd is incredibly fast for both compression and decompression, and offers significantly better ratios than `gzip`. Because we compress *after* chunking and deduplicating, we get the best of both worlds: deduplication of identical data, and compression of unique data.

## 4. Atomic Chunk Writes
- **Decision:** Chunks are written to a `.tmp` file first, and then renamed to their final SHA-256 hash filename using `os.rename()`.
- **Rationale:** If a user unplugs their computer or the script is killed halfway through writing a chunk, the disk would contain a corrupted, half-written chunk. Because `os.rename()` is guaranteed to be atomic by POSIX filesystems, a chunk only ever appears in the vault if it was written 100% successfully.

## 5. Strict Restore Verification
- **Decision:** `sdel` computes a `full_file_hash` when deleting a file and stores it in the database. During `restore`, it recalculates the hash of the reconstructed file. The database record is *only* deleted if the hashes match perfectly.
- **Rationale:** If the disk fills up during a restore, or the script crashes, the restored file will be incomplete. If we blindly deleted the vault record anyway, the user would suffer permanent data loss. This strict verification guarantees that the vault copy is never destroyed until the real file is safely back on the user's disk.

## 6. Query-on-GC (Mark-and-Sweep) instead of Ref-Counting
- **Decision:** The database does *not* maintain a `refcount` column to track how many files use a specific chunk. Instead, Garbage Collection (GC) sweeps physical chunks by querying the database dynamically to see if the chunk's hash is still referenced by any file.
- **Rationale:** Reference counters in databases are notoriously fragile. If a script crashes before decrementing a counter, the chunk is permanently leaked. A Mark-and-Sweep approach is stateless and self-healing: it always calculates the true, absolute state of the vault.

## 7. High-Speed RAM Sweeping (Python Sets)
- **Decision:** The Garbage Collector loads all active chunk hashes from the database into a Python `set` for instant $O(1)$ memory lookups, rather than querying SQLite for every single physical file on disk.
- **Rationale:** We explicitly traded a tiny amount of RAM for a massive reduction in Disk I/O. Querying SQLite 100,000 times for 100,000 physical chunks would cause immense CPU and read/write overhead. Since a Python `set` of 30,000 SHA-256 strings only consumes ~6MB of cheap RAM, the in-memory set approach is vastly superior for performance on modern hardware without thrashing the disk.

## 8. The 1-Hour Concurrency Safety Buffer
- **Decision:** The Garbage Collector ignores any orphaned chunk that was modified less than 1 hour ago.
- **Rationale:** **Race Condition Prevention.** If User A is deleting a massive 10GB file in Terminal A, physical chunks are being written to disk *before* the database record is committed. If User B runs `sdel gc` in Terminal B at the exact same time, the GC would see those chunks, realize they aren't in the database yet, and delete them! The 1-hour delay perfectly solves this race condition without requiring complex, system-wide database locks.
