"""
ingest.py — Load recipe JSON files into a SQLite database with FTS5 search support.

Usage:
    python -m src.ingest [--db data/recipes.db] [--limit N] [--force]
"""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Allow running directly via `python src/ingest.py` from any directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.normalize import normalize_ingredient, count_steps

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCES = [
    {"file": "recipes_raw_nosource_ar.json", "prefix": "ar"},
    {"file": "recipes_raw_nosource_epi.json", "prefix": "epi"},
    {"file": "recipes_raw_nosource_fn.json",  "prefix": "fn"},
]

BATCH_SIZE = 500  # rows per transaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_recipe_id(source_prefix: str, orig_key: str) -> str:
    """SHA-256 of 'prefix:orig_key', take first 16 hex chars. Prefix with source."""
    h = hashlib.sha256(f"{source_prefix}:{orig_key}".encode()).hexdigest()[:16]
    return f"{source_prefix}_{h}"


def find_source_file(filename: str) -> Path | None:
    """Check project root (and CWD) first, then data/raw/ subdirectory."""
    candidates = [
        Path(filename),
        PROJECT_ROOT / filename,
        Path("data") / "raw" / filename,
        PROJECT_ROOT / "data" / "raw" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

CREATE_RECIPES = """
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id        TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    orig_key         TEXT NOT NULL,
    title            TEXT NOT NULL,
    ingredients_raw  TEXT NOT NULL,
    instructions_raw TEXT NOT NULL,
    step_count       INTEGER NOT NULL DEFAULT 0,
    ingredient_count INTEGER NOT NULL DEFAULT 0
);
"""

CREATE_RECIPE_INGREDIENTS = """
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id TEXT NOT NULL REFERENCES recipes(recipe_id),
    raw_text  TEXT NOT NULL,
    norm_name TEXT NOT NULL,
    quantity  TEXT,
    unit      TEXT
);
"""

CREATE_IDX_RECIPE_ID = "CREATE INDEX IF NOT EXISTS idx_ri_recipe_id ON recipe_ingredients(recipe_id);"
CREATE_IDX_NORM_NAME = "CREATE INDEX IF NOT EXISTS idx_ri_norm_name ON recipe_ingredients(norm_name);"

CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
    recipe_id UNINDEXED,
    title,
    ingredients_text,
    instructions_raw
);
"""

DROP_ORDER = ["recipes_fts", "recipe_ingredients", "recipes"]


def setup_db(conn: sqlite3.Connection, force: bool) -> None:
    cur = conn.cursor()
    if force:
        for table in DROP_ORDER:
            logger.info("Dropping table %s (--force)", table)
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()

    cur.execute(CREATE_RECIPES)
    cur.execute(CREATE_RECIPE_INGREDIENTS)
    cur.execute(CREATE_IDX_RECIPE_ID)
    cur.execute(CREATE_IDX_NORM_NAME)
    cur.execute(CREATE_FTS)
    conn.commit()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_source(
    conn: sqlite3.Connection,
    source_file: Path,
    prefix: str,
    limit: int | None,
) -> tuple[int, int]:
    """
    Ingest one JSON source file. Returns (recipe_count, ingredient_row_count).
    """
    logger.info("Loading %s from %s", prefix, source_file)

    try:
        with open(source_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        logger.error("Failed to read %s: %s", source_file, exc)
        return 0, 0

    if not isinstance(data, dict):
        logger.warning("Unexpected top-level type in %s: %s — skipping", source_file, type(data).__name__)
        return 0, 0

    cur = conn.cursor()
    existing_ids: set[str] = {
        row[0] for row in cur.execute("SELECT recipe_id FROM recipes WHERE source = ?", (prefix,)).fetchall()
    }

    recipe_rows: list[tuple] = []
    ingredient_rows: list[tuple] = []
    recipe_count = 0
    ingredient_count_total = 0
    skipped = 0

    items = list(data.items())
    if limit is not None:
        items = items[:limit]

    for idx, (orig_key, recipe_obj) in enumerate(items):
        # --- Validate entry ---
        if recipe_obj is None or not isinstance(recipe_obj, dict):
            logger.debug("Skipping key %s: null or non-dict value", orig_key)
            skipped += 1
            continue

        title = recipe_obj.get("title") or ""
        if not isinstance(title, str):
            title = str(title)
        title = title.strip()
        if not title:
            logger.debug("Skipping key %s: missing/empty title", orig_key)
            skipped += 1
            continue

        raw_ingredients = recipe_obj.get("ingredients")
        raw_instructions = recipe_obj.get("instructions")

        # Coerce types
        if not isinstance(raw_ingredients, list):
            raw_ingredients = []
        if not isinstance(raw_instructions, str):
            raw_instructions = str(raw_instructions) if raw_instructions else ""

        # Skip if both ingredients and instructions are empty
        if not raw_ingredients and not raw_instructions.strip():
            logger.debug("Skipping key %s: both ingredients and instructions empty", orig_key)
            skipped += 1
            continue

        # --- Build recipe row ---
        recipe_id = make_recipe_id(prefix, orig_key)
        if recipe_id in existing_ids:
            skipped += 1
            continue
        existing_ids.add(recipe_id)
        step_count = count_steps(raw_instructions)
        ingredients_raw_json = json.dumps(raw_ingredients, ensure_ascii=False)
        ingredient_count = len(raw_ingredients)

        recipe_rows.append((
            recipe_id,
            prefix,
            orig_key,
            title,
            ingredients_raw_json,
            raw_instructions,
            step_count,
            ingredient_count,
        ))

        # --- Build ingredient rows ---
        valid_ing_count = 0
        for raw_text in raw_ingredients:
            if not isinstance(raw_text, str) or not raw_text.strip():
                continue
            try:
                norm_name, quantity, unit = normalize_ingredient(raw_text)
            except Exception as exc:
                logger.debug("normalize_ingredient failed for %r: %s", raw_text, exc)
                norm_name, quantity, unit = raw_text.strip().lower(), None, None

            if not norm_name:
                continue
            valid_ing_count += 1
            ingredient_rows.append((recipe_id, raw_text, norm_name, quantity, unit))

        recipe_count += 1
        ingredient_count_total += ingredient_count

        # Progress
        if recipe_count % 1000 == 0:
            print(f"  [{prefix}] {recipe_count} recipes processed…", flush=True)

        # Flush recipes batch (must happen before ingredients due to foreign key)
        if len(recipe_rows) >= BATCH_SIZE:
            _flush_recipes(cur, conn, recipe_rows)
            recipe_rows = []

        # Flush ingredient batch (flush pending recipes first so FK holds)
        if len(ingredient_rows) >= BATCH_SIZE:
            if recipe_rows:
                _flush_recipes(cur, conn, recipe_rows)
                recipe_rows = []
            _flush_ingredients(cur, conn, ingredient_rows)
            ingredient_rows = []

    # Flush remainders
    if recipe_rows:
        _flush_recipes(cur, conn, recipe_rows)
    if ingredient_rows:
        _flush_ingredients(cur, conn, ingredient_rows)

    logger.info(
        "[%s] Loaded %d recipes (%d skipped), %d ingredient rows",
        prefix, recipe_count, skipped, ingredient_count_total,
    )
    return recipe_count, ingredient_count_total


def _flush_recipes(cur: sqlite3.Cursor, conn: sqlite3.Connection, rows: list[tuple]) -> None:
    try:
        cur.executemany(
            """
            INSERT INTO recipes
                (recipe_id, source, orig_key, title, ingredients_raw, instructions_raw, step_count, ingredient_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # Fallback: insert one-by-one to skip duplicates
        conn.rollback()
        for row in rows:
            try:
                cur.execute(
                    """
                    INSERT INTO recipes
                        (recipe_id, source, orig_key, title, ingredients_raw, instructions_raw, step_count, ingredient_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                conn.commit()
            except sqlite3.IntegrityError:
                logger.debug("Duplicate recipe_id %s — skipping", row[0])
                conn.rollback()


def _flush_ingredients(cur: sqlite3.Cursor, conn: sqlite3.Connection, rows: list[tuple]) -> None:
    cur.executemany(
        """
        INSERT INTO recipe_ingredients (recipe_id, raw_text, norm_name, quantity, unit)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def populate_fts(conn: sqlite3.Connection) -> None:
    """Populate FTS5 table from the recipes + recipe_ingredients tables."""
    logger.info("Populating FTS5 index…")
    cur = conn.cursor()
    cur.execute("DELETE FROM recipes_fts")
    cur.execute(
        """
        INSERT INTO recipes_fts(recipe_id, title, ingredients_text, instructions_raw)
        SELECT
            r.recipe_id,
            r.title,
            COALESCE(
                (SELECT GROUP_CONCAT(ri.norm_name, ' ')
                 FROM recipe_ingredients ri
                 WHERE ri.recipe_id = r.recipe_id),
                ''
            ),
            r.instructions_raw
        FROM recipes r
        """
    )
    conn.commit()
    logger.info("FTS5 index populated.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest recipe JSON files into SQLite.")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max recipes per source file (for quick testing).",
    )
    parser.add_argument(
        "--db", default="data/recipes.db",
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Drop and recreate tables if they exist.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    setup_db(conn, force=args.force)

    total_recipes = 0
    total_ingredients = 0

    for source in SOURCES:
        filename = source["file"]
        prefix = source["prefix"]

        source_path = find_source_file(filename)
        if source_path is None:
            logger.warning("Source file not found: %s — skipping", filename)
            continue

        r_count, i_count = ingest_source(conn, source_path, prefix, args.limit)
        total_recipes += r_count
        total_ingredients += i_count

    populate_fts(conn)
    conn.close()

    logger.info(
        "Database ready at %s — %d recipes, %d ingredient rows",
        db_path, total_recipes, total_ingredients,
    )


if __name__ == "__main__":
    main()
