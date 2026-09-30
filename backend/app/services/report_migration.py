from sqlalchemy import inspect, text


def ensure_report_columns(engine):
    """Nullable additions preserve historical reports; no inferred evidence backfill."""
    additions = {
        "scans": {"analysis_version": "VARCHAR(64)", "source_commit": "VARCHAR(64)"},
        "issues": {"comparison_key": "VARCHAR(64)", "analyzer_metadata": "JSON"},
    }
    with engine.begin() as connection:
        for table, definitions in additions.items():
            columns = {c["name"] for c in inspect(connection).get_columns(table)}
            for name, definition in definitions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
