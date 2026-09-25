"""Deterministic SQL safety gate (no LLM in this path).

The model is untrusted: it produces text, and that text must survive this
pipeline before touching the database. String matching on "DROP" is not a
security control — every check below walks the sqlglot AST.

Stages: strip comments -> exactly one statement -> SELECT/UNION only ->
CTE-aware table allowlist -> per-table column allowlist -> dangerous
function denylist -> LIMIT required (injected when missing, capped).
"""
import re

import sqlglot
from sqlglot import exp

from .schema import ALLOWED_COLUMNS, ALLOWED_TABLES, MAX_SQL_ROWS

_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

# SQLite-specific hazards: file access, extension loading, meta commands.
DENIED_FUNCTIONS = frozenset({
    "LOAD_EXTENSION", "READFILE", "WRITEFILE", "EDIT", "DELETEFILE",
    "SQLITE_COMPILEOPTION_USED", "SQLITE_COMPILEOPTION_GET",
    "SQLITE_SOURCE_ID", "SQLITE_VERSION",
})


def _strip_comments(sql: str) -> str:
    return _COMMENT_RE.sub(" ", sql).strip()


def validate_sql(sql: str) -> tuple:
    """Return (ok, errors, normalized_sql). Fail closed: any doubt denies."""
    errors: list = []
    cleaned = _strip_comments(sql or "")
    if not cleaned:
        return False, ["Empty query."], None

    try:
        statements = [s for s in sqlglot.parse(cleaned, read="sqlite") if s is not None]
    except Exception as e:
        return False, [f"SQL parse error: {e}"], None
    if len(statements) != 1:
        return False, [f"Must contain exactly one statement, found {len(statements)}."], None
    stmt = statements[0]

    # Read-only statement types only. This one check kills INSERT/UPDATE/
    # DELETE/DROP/ALTER/CREATE/TRUNCATE/ATTACH/PRAGMA/VACUUM/GRANT.
    if not isinstance(stmt, (exp.Select, exp.Union)):
        return False, [f"Only read-only SELECT queries are allowed. Received: {type(stmt).__name__}."], None

    # CTE-aware table allowlist: CTE/subquery aliases are not tables.
    cte_names = set()
    for cte in stmt.find_all(exp.CTE):
        alias = cte.args.get("alias")
        name = alias.name if alias is not None else (cte.alias or "")
        if name:
            cte_names.add(name.upper())
    subquery_aliases = set()
    for sq in stmt.find_all(exp.Subquery):
        alias = sq.args.get("alias")
        if alias is not None and getattr(alias, "name", ""):
            subquery_aliases.add(alias.name.upper())
    known_aliases = cte_names | subquery_aliases

    tables = set()
    for t in stmt.find_all(exp.Table):
        name = (t.name or "").upper()
        if name and name not in known_aliases:
            tables.add(name)
    allowed_upper = {t.upper() for t in ALLOWED_TABLES}
    unknown = tables - allowed_upper
    if unknown:
        errors.append(f"Query references non-allowlisted tables: {sorted(unknown)}.")

    # Per-table column allowlist. Columns qualified by a CTE/derived alias
    # are covered by the inner query's own validation (find_all is recursive).
    table_of_alias: dict = {}
    for t in stmt.find_all(exp.Table):
        alias = t.args.get("alias")
        if alias is not None and getattr(alias, "name", ""):
            table_of_alias[alias.name.upper()] = (t.name or "").upper()
    physical_upper = {t.upper(): t for t in ALLOWED_TABLES}

    # SELECT-list aliases (e.g. ORDER BY peak) are defined by the query
    # itself, whose underlying expression is validated separately.
    aliases = set()
    for a in stmt.find_all(exp.Alias):
        if getattr(a, "alias", ""):
            aliases.add(a.alias.upper())

    for col in stmt.find_all(exp.Column):
        if isinstance(col.this, exp.Star):
            continue  # handled by the star rule below
        cname = (col.name or "").upper()
        if not cname:
            continue
        qualifier = (col.table or "").upper()
        if qualifier in known_aliases:
            continue
        if not qualifier and cname in aliases:
            continue
        if qualifier:
            real = table_of_alias.get(qualifier, qualifier)
            cols = ALLOWED_COLUMNS.get(physical_upper.get(real, real), None)
            if cols is None or cname not in {c.upper() for c in cols}:
                errors.append(f"Unknown column '{col.name}' for table '{col.table}'.")
        else:
            if not any(cname in {c.upper() for c in cols} for cols in ALLOWED_COLUMNS.values()):
                errors.append(f"Unknown column '{col.name}'.")

    # No SELECT * (can't enumerate what * returns); COUNT(*) is the exception.
    for star in stmt.find_all(exp.Star):
        parent = star.parent
        if not (isinstance(parent, exp.Count) or
                (isinstance(parent, exp.Column) and isinstance(parent.parent, exp.Count))):
            errors.append("SELECT * is not allowed; name explicit columns.")
            break

    # Dangerous functions (sqlglot parses unknown functions as Anonymous).
    for f in list(stmt.find_all(exp.Func)) + list(stmt.find_all(exp.Anonymous)):
        fname = ""
        try:
            if isinstance(f, exp.Anonymous):
                fname = str(f.this or "").upper()
            else:
                fname = (f.sql_name() or "").upper()
        except Exception:
            fname = type(f).__name__.upper()
        if fname in DENIED_FUNCTIONS or fname.startswith("PRAGMA_"):
            errors.append(f"Blocked function: {fname}.")
            break

    # LIMIT required; inject when missing, cap when present.
    limit = stmt.args.get("limit")
    if limit is None:
        stmt.set("limit", exp.Limit(expression=exp.Literal.number(MAX_SQL_ROWS)))
    else:
        lit = limit.args.get("expression")
        try:
            n = int(lit.name) if isinstance(lit, exp.Literal) else None
        except (TypeError, ValueError):
            n = None
        if n is None or n < 1:
            errors.append("LIMIT must be a fixed positive integer.")
        elif n > MAX_SQL_ROWS:
            errors.append(f"LIMIT exceeds the {MAX_SQL_ROWS}-row cap.")

    if errors:
        return False, errors, None
    return True, [], stmt.sql(dialect="sqlite")
