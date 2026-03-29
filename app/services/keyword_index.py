from pathlib import Path
from typing import Any
import sqlite3


FTS_TABLE = "chunks"


def build_keyword_index(chunks: list[dict[str, Any]], db_path: Path) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as connection:
        _create_fts_table(connection)
        connection.executemany(
            f"""
            INSERT INTO {FTS_TABLE} (
                chunk_id,
                document_id,
                title,
                path,
                text,
                article_no,
                chapter_title,
                region,
                promulgated_on,
                effective_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk["chunk_id"],
                    chunk.get("document_id"),
                    chunk.get("title"),
                    chunk.get("path"),
                    chunk.get("text"),
                    chunk.get("article_no"),
                    chunk.get("chapter_title"),
                    chunk.get("region"),
                    chunk.get("promulgated_on"),
                    chunk.get("effective_on"),
                )
                for chunk in chunks
            ],
        )

    return db_path


def search_keyword_index(
    query: str,
    db_path: Path,
    *,
    top_k: int = 10,
    region: str | None = None,
    promulgated_on: str | None = None,
    effective_on: str | None = None,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    normalized_query = query.strip()
    if not normalized_query:
        return []

    sql = f"""
        SELECT
            chunk_id,
            document_id,
            title,
            path,
            text,
            article_no,
            chapter_title,
            region,
            promulgated_on,
            effective_on,
            bm25({FTS_TABLE}) AS score
        FROM {FTS_TABLE}
        WHERE {FTS_TABLE} MATCH ?
    """
    parameters: list[Any] = [normalized_query]

    if region is not None:
        sql += " AND region = ?"
        parameters.append(region)
    if promulgated_on is not None:
        sql += " AND promulgated_on = ?"
        parameters.append(promulgated_on)
    if effective_on is not None:
        sql += " AND effective_on = ?"
        parameters.append(effective_on)

    sql += " ORDER BY score LIMIT ?"
    parameters.append(top_k)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.OperationalError:
            rows = []

        if rows:
            return [dict(row) for row in rows]

        like_sql = f"""
            SELECT
                chunk_id,
                document_id,
                title,
                path,
                text,
                article_no,
                chapter_title,
                region,
                promulgated_on,
                effective_on,
                0.0 AS score
            FROM {FTS_TABLE}
            WHERE (title LIKE ? OR path LIKE ? OR text LIKE ?)
        """
        like_parameters: list[Any] = [
            f"%{normalized_query}%",
            f"%{normalized_query}%",
            f"%{normalized_query}%",
        ]
        if region is not None:
            like_sql += " AND region = ?"
            like_parameters.append(region)
        if promulgated_on is not None:
            like_sql += " AND promulgated_on = ?"
            like_parameters.append(promulgated_on)
        if effective_on is not None:
            like_sql += " AND effective_on = ?"
            like_parameters.append(effective_on)

        like_sql += " ORDER BY length(text), chunk_id LIMIT ?"
        like_parameters.append(top_k)
        rows = connection.execute(like_sql, like_parameters).fetchall()

    return [dict(row) for row in rows]


def _create_fts_table(connection: sqlite3.Connection) -> None:
    table_sql = f"""
        CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5(
            chunk_id UNINDEXED,
            document_id UNINDEXED,
            title,
            path,
            text,
            article_no UNINDEXED,
            chapter_title UNINDEXED,
            region UNINDEXED,
            promulgated_on UNINDEXED,
            effective_on UNINDEXED%s
        )
    """
    try:
        connection.execute(table_sql % ", tokenize='trigram'")
    except sqlite3.OperationalError:
        connection.execute(table_sql % "")
