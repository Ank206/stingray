import sqlite3
from .config import DB_PATH, STORE_DIR

def init_db():
    """Initializes the database and storage directories."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deleted_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT NOT NULL,
                original_size INTEGER NOT NULL,
                permissions INTEGER NOT NULL,
                last_modified REAL NOT NULL,
                deleted_at TEXT NOT NULL,
                full_file_hash TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_chunks (
                file_id INTEGER NOT NULL,
                chunk_hash TEXT NOT NULL,
                chunk_order INTEGER NOT NULL,
                FOREIGN KEY(file_id) REFERENCES deleted_files(id)
            )
        """)
        
        # Create an index to make GC and lookups faster
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_hash ON file_chunks(chunk_hash)")
        
        conn.commit()
