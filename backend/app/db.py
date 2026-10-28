import sqlite3, hashlib
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, title TEXT, authors TEXT, year INTEGER, abstract TEXT,
 keywords TEXT, filename TEXT, sha256 TEXT UNIQUE, status TEXT, error TEXT,
 scanned INTEGER DEFAULT 0, page_count INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chunks(
 id TEXT PRIMARY KEY, doc_id TEXT, page INTEGER, offset_chars INTEGER, text TEXT,
 FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS entities(
 id TEXT PRIMARY KEY, doc_id TEXT, type TEXT, name TEXT, normalized TEXT,
 page INTEGER, snippet TEXT, confidence REAL, method TEXT,
 FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS relationships(
 id TEXT PRIMARY KEY, doc_id TEXT, source_type TEXT, source_name TEXT,
 relation TEXT, target_type TEXT, target_name TEXT, page INTEGER,
 snippet TEXT, confidence REAL, method TEXT, verified TEXT DEFAULT 'heuristic',
 FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS questions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, intent TEXT,
 answer TEXT, citations TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS gap_feedback(
 gap_key TEXT PRIMARY KEY, verdict TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

def connect():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    c = connect()
    c.executescript(SCHEMA)
    c.commit(); c.close()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
