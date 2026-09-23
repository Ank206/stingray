# AI Agent Onboarding Context

If you are an AI agent picking up this codebase for future iterations, please read this entirely before making modifications.

## Project Vision
`sdel` is a bulletproof, systems-level replacement for the Unix `rm` command. It does not just move files to a trash folder; it chunks them into 1MB blocks, deduplicates identical blocks, compresses them via Zstandard, and stores them in a central vault (`~/.sdel/chunks/`) tracked by a SQLite database. 

## Architectural Nuances (Do Not Break These!)
1. **Garbage Collection Safety:** We intentionally *do not* rely on SQLite foreign-key cascading or explicit `refcount` columns. Instead, physical chunks are swept lazily (Mark-and-Sweep). We use a **1-hour modification time delay** in `core.py -> garbage_collect` to avoid deleting chunks that are actively being written by parallel `sdel` commands. Do not optimize this delay away.
2. **Atomic Writes:** Chunk compression writes directly to a `.tmp` file and calls `.rename()` to prevent silent corruption if the script crashes. Maintain this pattern.
3. **Restore Integrity:** `restore_file` acts like a recycle bin (it deletes the vault records after restoration). However, it calculates a `full_file_hash` over the decompressed stream and strictly verifies it against the DB *before* it deletes anything. If verification fails, it aborts immediately to prevent permanent data loss. 

## Current Limitations / Future Work
- **Folders:** Recursive folder deletion (`sdel folder/`) is not supported yet. Currently, `sdel` relies on shell globbing (`sdel *`) to delete multiple files. If tasked to add folder support, remember to consider how directory structures will be recursively serialized into the SQLite schema.
- **Symlinks:** `Path.resolve()` is currently used, which means `sdel` deletes the symlink's target, not the symlink itself. Future iterations should check `path.is_symlink()` and handle them natively.
- **Version History:** If a user deletes the same file path multiple times, multiple rows exist in the DB. Currently, `restore` just pulls the latest version (`ORDER BY deleted_at DESC LIMIT 1`). Future agents could add a `--version` flag to let users restore specific historical snapshots.
- **Empty Files:** (0 bytes) currently chunk to 0 chunks, which is handled perfectly by the existing code but could cause edge-case bugs if modified incorrectly.
