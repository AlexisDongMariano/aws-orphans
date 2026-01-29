"""Simple Postgres access for orphaned security groups. Uses DATABASE_URL env var."""

import os
from contextlib import contextmanager
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

TABLE = "orphaned_sgs"
TABLE_EIPS = "orphaned_eips"
TABLE_EBS = "unattached_ebs"


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("Set DATABASE_URL (e.g. postgresql://user:pass@localhost:5432/dbname)")
    return url


@contextmanager
def get_connection():
    conn = psycopg2.connect(get_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_table(conn) -> None:
    conn.cursor().execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            id SERIAL PRIMARY KEY,
            region TEXT NOT NULL,
            group_id TEXT NOT NULL,
            group_name TEXT NOT NULL,
            description TEXT,
            vpc_id TEXT,
            console_url TEXT NOT NULL,
            scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def truncate_and_insert(conn, rows: list[dict]) -> None:
    """Replace all rows. Each row: region, group_id, group_name, description, vpc_id, console_url."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE}")
    scanned_at = datetime.utcnow()
    for r in rows:
        cur.execute(
            f"""
            INSERT INTO {TABLE} (region, group_id, group_name, description, vpc_id, console_url, scanned_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                r["region"],
                r["group_id"],
                r["group_name"],
                r.get("description") or "",
                r.get("vpc_id"),
                r["console_url"],
                scanned_at,
            ),
        )


def fetch_all(conn) -> list[dict]:
    """Return all orphaned SGs as list of dicts."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT region, group_id, group_name, description, vpc_id, console_url, scanned_at FROM {TABLE} ORDER BY region, group_id")
        return [dict(row) for row in cur.fetchall()]


# --- Orphaned Elastic IPs ---

def create_table_eips(conn) -> None:
    conn.cursor().execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_EIPS} (
            id SERIAL PRIMARY KEY,
            region TEXT NOT NULL,
            allocation_id TEXT NOT NULL,
            public_ip TEXT NOT NULL,
            domain TEXT NOT NULL,
            console_url TEXT NOT NULL,
            scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def truncate_and_insert_eips(conn, rows: list[dict]) -> None:
    """Replace all EIP rows. Each row: region, allocation_id, public_ip, domain, console_url."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_EIPS}")
    scanned_at = datetime.utcnow()
    for r in rows:
        cur.execute(
            f"""
            INSERT INTO {TABLE_EIPS} (region, allocation_id, public_ip, domain, console_url, scanned_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                r["region"],
                r["allocation_id"],
                r["public_ip"],
                r.get("domain", "vpc"),
                r["console_url"],
                scanned_at,
            ),
        )


def fetch_all_eips(conn) -> list[dict]:
    """Return all orphaned EIPs as list of dicts."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT region, allocation_id, public_ip, domain, console_url, scanned_at FROM {TABLE_EIPS} ORDER BY region, allocation_id")
        return [dict(row) for row in cur.fetchall()]


# --- Unattached EBS Volumes ---

def create_table_ebs(conn) -> None:
    conn.cursor().execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_EBS} (
            id SERIAL PRIMARY KEY,
            region TEXT NOT NULL,
            volume_id TEXT NOT NULL,
            size_gb INTEGER NOT NULL,
            volume_type TEXT NOT NULL,
            availability_zone TEXT NOT NULL,
            create_time TEXT,
            console_url TEXT NOT NULL,
            scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def truncate_and_insert_ebs(conn, rows: list[dict]) -> None:
    """Replace all EBS rows."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_EBS}")
    scanned_at = datetime.utcnow()
    for r in rows:
        cur.execute(
            f"""
            INSERT INTO {TABLE_EBS} (region, volume_id, size_gb, volume_type, availability_zone, create_time, console_url, scanned_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                r["region"],
                r["volume_id"],
                r.get("size_gb", 0),
                r.get("volume_type", ""),
                r.get("availability_zone", ""),
                r.get("create_time", ""),
                r["console_url"],
                scanned_at,
            ),
        )


def fetch_all_ebs(conn) -> list[dict]:
    """Return all unattached EBS volumes as list of dicts."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT region, volume_id, size_gb, volume_type, availability_zone, create_time, console_url, scanned_at FROM {TABLE_EBS} ORDER BY region, volume_id")
        return [dict(row) for row in cur.fetchall()]
