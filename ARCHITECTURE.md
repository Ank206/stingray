# sdel Architecture

## Overview
`sdel` is a safe alternative to `rm`. It intercepts file deletions, compresses them using Zstandard, and stores them in a central vault (`~/.sdel/store`). A SQLite database (`~/.sdel/index.db`) keeps track of metadata.

## Current State (Step 3: Content-Addressed Chunking)
- **Database (`deleted_files`)**: Stores `original_path`, `original_size`, `permissions`, `last_modified`, `deleted_at`, and a `full_file_hash` for integrity checks.
- **Database (`file_chunks`)**: A relational mapping table (`file_id`, `chunk_hash`, `chunk_order`) linking files to their constituent parts.
- **Vault (`~/.sdel/chunks/`)**: Stores deduplicated 1MB chunks of data. The filename is the SHA-256 hash of the raw chunk. Each chunk is individually compressed via Zstandard using atomic writes (`.tmp` renaming) to prevent corruption.

## Upcoming (Step 4: Garbage Collection)
- Implement an expiry mechanism to prune `deleted_files` entries older than N days.
- Implement a GC pass that queries `file_chunks` to find orphaned hashes and permanently deletes unreferenced physical chunks from the vault.
