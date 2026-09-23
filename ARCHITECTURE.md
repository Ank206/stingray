# sdel Architecture

## Overview
`sdel` is a safe, deduplicating alternative to `rm`. It intercepts file deletions, splits them into 1MB chunks, hashes them for deduplication, compresses them using Zstandard, and stores them in a central vault (`~/.sdel/chunks`). A SQLite database (`~/.sdel/index.db`) keeps track of metadata and chunk assembly orders.

## Core Design Principles
1. **Never Lose Data:** Always strictly verify full-file hashes (SHA-256) upon restoration before finalizing deletes from the vault. 
2. **Prevent Corruption:** All chunks are written using atomic `.tmp` renaming to prevent silent corruption from interrupted scripts.
3. **Save Space:** Chunk-based Content Addressed Storage (CAS) with Zstandard achieves aggressive compression and deduplication on shared data.
4. **Self-Healing GC:** Zero-RAM streaming Garbage Collection handles orphaned physical chunks safely using a 1-hour concurrency delay to prevent race conditions.

## Components (`sdel/`)
- `cli.py`: Uses `argparse` to route commands (`delete`, `restore`, `list`, `gc`, `stats`). Supports shell globbing (multiple files via `*`).
- `core.py`: Contains the heavy lifting:
  - `delete_file`: Chunks the file (1MB), hashes, compresses (Zstd), deduplicates against existing hashes, writes atomically, and inserts DB records.
  - `restore_file`: Reconstructs the file from chunks, strictly checks `full_file_hash`, restores original permissions and timestamps, and runs an Auto-GC to prune the DB and orphaned chunks.
  - `garbage_collect`: A two-phase Mark-and-Sweep. Prunes expired DB rows, then uses an $O(1)$ memory generator (`os.scandir`) to detect and unlink unreferenced physical chunks that are >1 hour old.
  - `stats`: Analyzes `original_size` vs physical vault size to show space savings.
- `db.py`: Bootstraps the SQLite relational schema.
- `config.py`: Hardcoded paths and constants (`~/.sdel/`, `CHUNK_SIZE`).

## Database Schema
- **Table `deleted_files`**: 
  - `id` (PK)
  - `original_path`
  - `original_size`
  - `permissions`
  - `last_modified`
  - `deleted_at`
  - `full_file_hash` (SHA-256 for post-restore integrity check)
- **Table `file_chunks`**:
  - `id` (PK)
  - `file_id` (FK to `deleted_files`)
  - `chunk_hash`
  - `chunk_order` (integer ensuring deterministic reconstruction)
