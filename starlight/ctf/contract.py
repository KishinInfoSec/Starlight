"""Schema contract: tables/columns that code outside Django (scripts, other services) may rely on in plain SQL."""
import json
from pathlib import Path

from django.db import connection as default_connection

CONTRACT_PATH = Path(__file__).with_name("schema_contract.json")


def load_contract(path=CONTRACT_PATH):
    return json.loads(Path(path).read_text())


def missing_from_database(contract, connection=default_connection):
    """Return 'table.column' / 'table (table)' entries the database lacks."""
    problems = []
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
        for table, columns in contract["tables"].items():
            if table not in existing:
                problems.append(f"{table} (table)")
                continue
            have = {c.name for c in connection.introspection.get_table_description(cursor, table)}
            problems.extend(f"{table}.{c}" for c in columns if c not in have)
    return problems
