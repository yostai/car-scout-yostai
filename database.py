"""
Car Scout - SQLite database operations.
Tracks seen listings so we only notify about new ones.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'car_scout.db')


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS listings (
                id          TEXT PRIMARY KEY,
                source      TEXT,
                vehicle     TEXT,
                title       TEXT,
                url         TEXT,
                price       TEXT,
                mileage     INTEGER,
                location    TEXT,
                image_url   TEXT,
                first_seen  TEXT,
                last_seen   TEXT
            );

            CREATE TABLE IF NOT EXISTS seen (
                listing_id  TEXT PRIMARY KEY,
                first_seen  TEXT
            );
        """)
    log.info("Database initialized")


def save_listings(listings):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        for l in listings:
            conn.execute("""
                INSERT INTO listings (id, source, vehicle, title, url, price, mileage,
                                      location, image_url, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT first_seen FROM listings WHERE id = ?), ?
                ), ?)
                ON CONFLICT(id) DO UPDATE SET
                    price = excluded.price,
                    mileage = excluded.mileage,
                    last_seen = excluded.last_seen
            """, (
                l['id'], l['source'], l['vehicle'], l['title'], l['url'],
                l.get('price'), l.get('mileage'), l.get('location'), l.get('image_url'),
                l['id'], now, now
            ))


def get_new_listings(scraped_listings):
    """Return only listings not previously seen."""
    if not scraped_listings:
        return []
    with get_conn() as conn:
        ids = [l['id'] for l in scraped_listings]
        placeholders = ','.join('?' * len(ids))
        seen_rows = conn.execute(
            f"SELECT listing_id FROM seen WHERE listing_id IN ({placeholders})", ids
        ).fetchall()
        seen_ids = {row[0] for row in seen_rows}
    return [l for l in scraped_listings if l['id'] not in seen_ids]


def mark_seen(listing_ids):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO seen (listing_id, first_seen) VALUES (?, ?)",
            [(lid, now) for lid in listing_ids]
        )


def get_all_listings(days=30):
    """Return all listings seen in the last N days, newest first."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM listings WHERE last_seen >= ? ORDER BY first_seen DESC
        """, (cutoff,)).fetchall()
    return [dict(row) for row in rows]
