"""The SQL smart board's engine: real queries against a real database.

The SQL lessons used to end in a textarea and a model answer to compare
yourself against. That teaches you to recognise a correct query, which is not
the same skill as writing one — you can read a JOIN and agree with it all day
and still not know what it did to your rows.

This runs the student's SQL for real, on a real database, and shows the rows
that came back. Everything in this module is deterministic: no model call, no
token, no per-student cost. A thousand learners running a thousand queries
costs exactly what one does, which is why the runner can be free while the
written explanation stays paid.

Safety. The query never touches the product database. Every run builds a
fresh in-memory SQLite from the seed below, runs one statement against it,
and throws the whole thing away. On top of that the connection is made
read-only by an authorizer that permits SELECT and READ and denies everything
else, so INSERT, DROP, ATTACH and PRAGMA fail inside SQLite itself rather than
relying on us to spot them in the text. There is nothing to inject into: the
database is a toy, it is per-request, and it is gone before the response is
written.
"""
import re
import sqlite3
import time

# Rows returned to the page. A student who writes a cartesian product should
# see that it exploded, not wait for 40,000 rows to render.
MAX_ROWS = 200
# SQLite VM steps before we pull the plug. A recursive CTE with no base case
# is the usual way to hang this, and it is a mistake worth catching quickly.
MAX_STEPS = 400_000
MAX_SQL = 4000


# --------------------------------------------------------------------------
# The sample database
# --------------------------------------------------------------------------
# A shop, because everyone has bought something and nobody needs the domain
# explained. Two things here are deliberate and load-bearing:
#
#   * Priya, Sam and Nadia have no orders at all. Without customers who never
#     bought anything, INNER JOIN and LEFT JOIN return identical rows and the
#     single most important JOIN lesson is invisible.
#   * Two orders are cancelled. Without them, WHERE before GROUP BY and WHERE
#     after it give the same totals, and HAVING looks like pointless ceremony.
SCHEMA = """
CREATE TABLE customers (
  id      INTEGER PRIMARY KEY,
  name    TEXT    NOT NULL,
  city    TEXT    NOT NULL,
  joined  TEXT    NOT NULL
);
CREATE TABLE products (
  id       INTEGER PRIMARY KEY,
  title    TEXT    NOT NULL,
  category TEXT    NOT NULL,
  price    REAL    NOT NULL
);
CREATE TABLE orders (
  id          INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  ordered_at  TEXT    NOT NULL,
  status      TEXT    NOT NULL
);
CREATE TABLE order_items (
  id         INTEGER PRIMARY KEY,
  order_id   INTEGER NOT NULL REFERENCES orders(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  qty        INTEGER NOT NULL
);
"""

CUSTOMERS = [
    (1, "Asha Menon", "Bengaluru", "2024-01-14"),
    (2, "Ravi Kumar", "Hyderabad", "2024-02-03"),
    (3, "Priya Nair", "Kochi", "2024-02-19"),
    (4, "Sam Fernandes", "Mumbai", "2024-03-08"),
    (5, "Divya Rao", "Bengaluru", "2024-03-22"),
    (6, "Imran Sheikh", "Delhi", "2024-04-01"),
    (7, "Nadia Khan", "Pune", "2024-04-17"),
    (8, "Tara Iyer", "Chennai", "2024-05-05"),
    (9, "Vikram Singh", "Delhi", "2024-05-28"),
    (10, "Meera Joshi", "Pune", "2024-06-11"),
]

PRODUCTS = [
    (1, "Mechanical keyboard", "electronics", 4500.0),
    (2, "Noise-cancelling headphones", "electronics", 8900.0),
    (3, "USB-C hub", "electronics", 2200.0),
    (4, "Standing desk", "furniture", 18500.0),
    (5, "Ergonomic chair", "furniture", 12400.0),
    (6, "Desk lamp", "furniture", 1900.0),
    (7, "Clean Code", "books", 650.0),
    (8, "Designing Data-Intensive Applications", "books", 1150.0),
    (9, "Notebook, ruled", "stationery", 120.0),
    (10, "Gel pen pack", "stationery", 260.0),
    # Dead stock, and deliberately so. Every other product appears in some
    # order, which meant "find the products nobody has ever ordered" returned
    # an empty result — an anti-join exercise whose answer is nothing teaches
    # nothing. Real catalogues always have one of these.
    (11, "Whiteboard marker, dry-wipe", "stationery", 180.0),
]

# (id, customer_id, ordered_at, status)
ORDERS = [
    (101, 1, "2024-06-02", "completed"),
    (102, 1, "2024-06-19", "completed"),
    (103, 2, "2024-06-21", "completed"),
    # Cancelled, and deliberately belonging to a customer who also has a
    # completed order: Ravi's totals change depending on whether the student
    # filtered on status, which is the mistake the HAVING exercise is hunting.
    (104, 2, "2024-07-01", "cancelled"),
    (105, 5, "2024-07-04", "completed"),
    (106, 5, "2024-07-15", "completed"),
    (107, 6, "2024-07-18", "pending"),
    (108, 8, "2024-07-22", "completed"),
    (109, 9, "2024-08-01", "completed"),
    (110, 9, "2024-08-09", "cancelled"),
    (111, 10, "2024-08-14", "completed"),
    (112, 1, "2024-08-20", "pending"),
]

# (id, order_id, product_id, qty)
ITEMS = [
    (1, 101, 1, 1), (2, 101, 3, 2),
    (3, 102, 7, 3),
    (4, 103, 2, 1), (5, 103, 9, 10),
    (6, 104, 4, 1),
    (7, 105, 5, 1), (8, 105, 6, 2),
    (9, 106, 8, 1),
    (10, 107, 1, 2),
    (11, 108, 4, 1), (12, 108, 5, 1), (13, 108, 6, 1),
    (14, 109, 10, 5),
    (15, 110, 2, 1),
    (16, 111, 3, 1), (17, 111, 9, 4),
    (18, 112, 8, 2),
]

TABLES = ("customers", "products", "orders", "order_items")


def _seed(conn):
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO products  VALUES (?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO orders    VALUES (?,?,?,?)", ORDERS)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?)", ITEMS)
    conn.commit()


# --------------------------------------------------------------------------
# Read-only enforcement
# --------------------------------------------------------------------------
# Getattr with a fallback because these constants have drifted between Python
# versions, and a missing name here would fail open — the authorizer would
# raise, we would catch it as a query error, and writes would go through.
_OK = sqlite3.SQLITE_OK
_DENY = sqlite3.SQLITE_DENY
_ALLOWED = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def _readonly(action, arg1, arg2, dbname, trigger):
    """Allow reading the four sample tables, refuse everything else.

    This is the real boundary, not a blocklist of scary words in the query
    text. A student who writes DROP TABLE customers gets "not authorized"
    from SQLite's own parser, which is both safer than regex and a better
    lesson than a lecture about what they are not allowed to type.

    Reads are checked by name as well, which closes sqlite_master. Nothing
    secret lives in it — this database is a toy and its schema is printed down
    the side of the page — but a sandbox that answers "what else is in here"
    is one table away from being interesting to the wrong person.

    Checked by prefix rather than against the four table names, which was the
    first attempt. SQLite reserves everything beginning "sqlite_" for its own
    internals, and it also asks permission to read the name of a CTE — so an
    allowlist of real tables refused every WITH RECURSIVE query on the board,
    which is one of the things an expert most needs to practise. The database
    is rebuilt per request and holds nothing but the sample data, so any name
    that is not SQLite's own is ours to read.
    """
    if action == sqlite3.SQLITE_READ:
        return _DENY if str(arg1 or "").lower().startswith("sqlite_") else _OK
    return _OK if action in _ALLOWED else _DENY


def _connect():
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    steps = {"n": 0}

    def guard():
        steps["n"] += 1
        return 1 if steps["n"] > MAX_STEPS // 1000 else 0

    conn.set_progress_handler(guard, 1000)
    conn.set_authorizer(_readonly)
    return conn


# --------------------------------------------------------------------------
# Friendlier errors
# --------------------------------------------------------------------------
# SQLite's messages are accurate and useless to a beginner. "no such column:
# cust_id" does not say that the column is called customer_id, or that the
# reason a bare name failed is that two joined tables both have one. Every
# rewrite here is a rule, not a guess, so it costs nothing and never invents.
_HINTS = (
    (r"no such column: (.+)", lambda m:
     f"There is no column called {m.group(1)}. Check the spelling against the "
     f"schema on the left — and if two tables in your query both have that "
     f"column, you have to say which one you mean, like orders.id."),
    (r"no such table: (.+)", lambda m:
     f"There is no table called {m.group(1)}. This database has four: "
     f"customers, products, orders and order_items."),
    (r"ambiguous column name: (.+)", lambda m:
     f"Both tables you joined have a column called {m.group(1)}, so SQLite "
     f"cannot tell which one you want. Put the table name in front of it."),
    (r"near \"(.+?)\": syntax error", lambda m:
     f"SQLite stopped at \"{m.group(1)}\". The mistake is usually just before "
     f"that word — a missing comma between columns, or a keyword in the wrong "
     f"order. The order is SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY."),
    (r"incomplete input", lambda m:
     "The query stops in the middle — an unclosed bracket or quote, usually."),
    (r"not authorized", lambda m:
     "This board runs SELECT, and only against the four sample tables — "
     "customers, products, orders and order_items. They are read-only so that "
     "everyone gets the same rows to reason about."),
    (r"misuse of aggregate|aggregate functions are not allowed", lambda m:
     "You cannot filter on SUM or COUNT in WHERE, because WHERE runs before "
     "the rows are grouped. Filter groups with HAVING instead."),
    (r"you can only execute one statement", lambda m:
     "Run one statement at a time. Drop the semicolon and anything after it."),
)


def friendly(msg):
    """Turn a SQLite error into something a learner can act on."""
    low = str(msg).strip()
    for pat, make in _HINTS:
        m = re.search(pat, low, re.I)
        if m:
            return make(m)
    return low


# --------------------------------------------------------------------------
# Running a query
# --------------------------------------------------------------------------
def run(sql, limit=MAX_ROWS):
    """Execute one SELECT and return columns, rows and how long it took.

    Never raises for a bad query: a syntax error is an ordinary outcome on a
    learning board and belongs in the response, not in a 500.
    """
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return {"ok": False, "error": "Write a query first.", "raw": ""}
    if len(sql) > MAX_SQL:
        return {"ok": False, "error": f"That query is longer than "
                f"{MAX_SQL} characters.", "raw": ""}

    conn = _connect()
    try:
        t0 = time.perf_counter()
        cur = conn.execute(sql)
        rows = cur.fetchmany(limit + 1)
        ms = (time.perf_counter() - t0) * 1000
        cols = [d[0] for d in (cur.description or [])]
        if cols == []:
            # A statement that returns no result set at all. Under the
            # authorizer this is nearly unreachable, but "it worked and showed
            # nothing" would be a confusing thing to display.
            return {"ok": False, "error": "That did not return any rows to "
                    "show. The board runs SELECT queries.", "raw": ""}
        more = len(rows) > limit
        out = [[_cell(v) for v in r] for r in rows[:limit]]
        return {"ok": True, "columns": cols, "rows": out, "count": len(out),
                "truncated": more, "ms": round(ms, 2)}
    except sqlite3.Error as e:
        return {"ok": False, "error": friendly(e), "raw": str(e)}
    except Exception as e:  # progress-handler abort surfaces here
        return {"ok": False, "error": "That query was still running after a "
                "long time, so it was stopped. An accidental cross join or a "
                "recursive query with no stopping point will do this.",
                "raw": type(e).__name__}
    finally:
        conn.close()


def _cell(v):
    if isinstance(v, bytes):
        return "<binary>"
    if isinstance(v, float):
        return round(v, 4)
    return v


def plan(sql):
    """The optimiser's own plan for a query.

    This is the one place a learner can watch an index stop being an
    abstraction: the same query reads SCAN customers before an index exists
    and SEARCH customers USING INDEX after, and the row count in the corner
    goes from ten to one. Real output from the real planner, not a story
    about what a planner would do.
    """
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return {"ok": False, "error": "Write a query first."}
    conn = _connect()
    try:
        rows = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
        steps = [r[-1] for r in rows]
        scans = [s for s in steps if s.strip().startswith("SCAN")]
        return {"ok": True, "steps": steps,
                "reading": ("Every SCAN is SQLite reading a whole table row by "
                            "row. On ten rows you will never feel it; on ten "
                            "million it is the difference between instant and "
                            "a timeout."
                            if scans else
                            "No full scans — SQLite found an index or a "
                            "primary key for every table it had to touch.")}
    except sqlite3.Error as e:
        return {"ok": False, "error": friendly(e)}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# What a JOIN actually did
# --------------------------------------------------------------------------
def join_trace(left, left_key, right, right_key, limit=40):
    """Pair up two tables on a key and report which rows found a partner.

    The board draws this as two columns with lines between them. It is worked
    out here, from the tables themselves, rather than by reading the student's
    SQL — parsing their query to guess their intent would be both hard and
    wrong, and the point of the picture is to show what the data does, which
    does not depend on how they wrote it.

    The unmatched list is the whole lesson. INNER JOIN drops those rows and
    LEFT JOIN keeps them with NULLs, and until you have seen which three
    customers vanish, the two are just different words.
    """
    if left not in TABLES or right not in TABLES:
        return {"ok": False, "error": "Unknown table."}
    conn = _connect()
    try:
        lcols = _columns(conn, left)
        rcols = _columns(conn, right)
        if left_key not in lcols or right_key not in rcols:
            return {"ok": False, "error": "Unknown column."}
        lrows = conn.execute(f"SELECT * FROM {left} LIMIT ?", (limit,)).fetchall()
        rrows = conn.execute(f"SELECT * FROM {right} LIMIT ?", (limit,)).fetchall()
        li, ri = lcols.index(left_key), rcols.index(right_key)

        pairs, matched_r = [], set()
        for a, lr in enumerate(lrows):
            for b, rr in enumerate(rrows):
                if lr[li] == rr[ri]:
                    pairs.append([a, b])
                    matched_r.add(b)
        lonely_l = sorted({a for a in range(len(lrows))}
                          - {p[0] for p in pairs})
        lonely_r = [b for b in range(len(rrows)) if b not in matched_r]
        return {
            "ok": True,
            "left": {"table": left, "key": left_key, "columns": lcols,
                     "rows": [[_cell(v) for v in r] for r in lrows]},
            "right": {"table": right, "key": right_key, "columns": rcols,
                      "rows": [[_cell(v) for v in r] for r in rrows]},
            "pairs": pairs,
            "unmatched_left": lonely_l,
            "unmatched_right": lonely_r,
            "reading": (
                f"{len(pairs)} rows come out of an INNER JOIN. "
                f"{len(lonely_l)} {left} rows match nothing on the right — "
                f"INNER JOIN throws those away, LEFT JOIN keeps them and fills "
                f"the {right} columns with NULL. That single difference is "
                f"most of what JOIN questions in interviews are testing."),
        }
    finally:
        conn.close()


def _columns(conn, table):
    cur = conn.execute(f"SELECT * FROM {table} LIMIT 0")
    return [d[0] for d in cur.description]


# --------------------------------------------------------------------------
# The walkthrough: what this query did, in the order it happened
# --------------------------------------------------------------------------
# The single most useful thing anyone can be told about SQL is that it does not
# run in the order it is written. You write SELECT first and it happens almost
# last, which is why "you cannot use an alias in WHERE" and "COUNT(*) belongs in
# HAVING" feel like arbitrary rules instead of consequences.
#
# So this is drawn for every query, not just the wrong ones, and it is drawn
# free. It is string inspection over a fixed set of four known table names —
# no model, no tokens, no latency. The AI explanation sits on top of this for
# the cases where a picture of the pipeline is not enough; it is not a
# replacement for it.
_STRINGS = re.compile(r"'[^']*'|\"[^\"]*\"")

_CLAUSES = [
    ("from", r"\bfrom\b", "FROM / JOIN",
     "SQLite collects the raw rows first. Nothing has been filtered yet — at "
     "this point the query is holding every row of every table it touches, "
     "which is why an accidental join can explode before any of your "
     "conditions get a chance to run."),
    ("where", r"\bwhere\b", "WHERE",
     "Rows are thrown out one at a time. This runs before any grouping, so it "
     "cannot see a COUNT or a SUM — those do not exist yet. It is also the "
     "cheapest place to filter, because everything after this works on less."),
    ("group", r"\bgroup\s+by\b", "GROUP BY",
     "The surviving rows are folded into one row per distinct value. After "
     "this the individual rows are gone; you can only ask about the groups."),
    ("having", r"\bhaving\b", "HAVING",
     "Now the groups themselves get filtered. This is the only place a COUNT "
     "or SUM can be tested, and the reason is just that the groups did not "
     "exist until the line above."),
    ("select", r"\bselect\b", "SELECT",
     "Only now are the output columns worked out. This is why an alias you "
     "invent here cannot be used in WHERE — WHERE had already finished long "
     "before the name existed."),
    ("order", r"\border\s+by\b", "ORDER BY",
     "The finished rows get sorted. Late, and deliberately so: sorting rows "
     "you are about to discard is wasted work."),
    ("limit", r"\blimit\b", "LIMIT",
     "The last cut. Everything above ran in full first — LIMIT 10 on an "
     "unindexed sort still sorted the whole table to find those ten."),
]


def walkthrough(sql, result=None):
    """A free, sketched account of what the student's own query just did.

    Returns steps in execution order plus a flow diagram of them, in the same
    {kind, nodes, edges} shape the main smart board already renders — labels
    and index pairs only, never markup.
    """
    raw = (sql or "").strip()
    if not raw:
        return {"ok": False}
    # Blank out string literals so a city called 'orders' is not read as a
    # table and WHERE inside a quoted value is not read as a clause.
    body = _STRINGS.sub("''", raw)
    low = body.lower()

    steps = []
    for key, pat, label, meaning in _CLAUSES:
        if not re.search(pat, low):
            continue
        note = meaning
        if key == "from":
            hit = [t for t in TABLES if re.search(rf"\b{t}\b", low)]
            if hit:
                conn = _connect()
                try:
                    counts = ", ".join(
                        f"{t} ({conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows)"
                        for t in hit)
                finally:
                    conn.close()
                note = f"Starting from {counts}. " + meaning
            if re.search(r"\bleft\s+join\b", low):
                note += (" You used LEFT JOIN, so rows on the left with no "
                         "partner on the right survive with NULLs rather than "
                         "being dropped.")
            elif re.search(r"\bjoin\b", low):
                note += (" You used an inner join, so any row without a match "
                         "on the other side is gone from here on — that is the "
                         "usual reason a total comes out lower than expected.")
        steps.append({"key": key, "label": label, "note": note})

    extras = []
    if re.search(r"\bover\s*\(", low):
        extras.append(
            "There is a window function in here. Unlike GROUP BY it ranks or "
            "totals across a set of rows without folding them together, so you "
            "keep every row and gain a column. That is how you answer 'where "
            "does each row sit within its own group' in one pass.")
    if re.search(r"\(\s*select\b", low):
        extras.append(
            "There is a subquery. The inner one runs first and its answer is "
            "handed to the outer one, which is why it can stand in for a "
            "value you do not know when you write the query.")
    if re.search(r"\bselect\s+\*", low):
        extras.append(
            "SELECT * asks for every column. Fine while you are exploring, and "
            "a habit worth losing before production: it moves data nobody "
            "reads, and it changes shape silently when someone adds a column.")
    if re.search(r"\bfrom\s+\w+\s*,\s*\w+", low) and "where" not in low:
        extras.append(
            "Two tables in FROM with no condition joining them is a cross "
            "join: every row paired with every row. It is almost never what "
            "anyone means, and it is the usual cause of a result far larger "
            "than either table.")

    out = {"ok": True, "steps": steps, "notes": extras,
           "stages": pipeline(raw)}
    if result and result.get("ok"):
        out["rows_out"] = result.get("count")
    return out


# --------------------------------------------------------------------------
# The pipeline: the student's own rows, at each stage of their own query
# --------------------------------------------------------------------------
# A drawing of a query is a drawing. This runs the query in stages and returns
# the real rows at each one, so a learner watches their own ten customers
# become six after WHERE and two after HAVING. Nothing is illustrated or
# approximated — every stage is a query that actually ran against the same
# database, which is why it can be trusted and why it costs nothing.
#
# Stages are built by cutting the query at its top-level clause keywords, so a
# keyword inside a subquery or a string never splits anything. Any stage that
# will not run is skipped rather than guessed at: some queries genuinely have
# no meaningful halfway point, and inventing one would be worse than omitting
# it.
_STAGE_WORDS = ("where", "group by", "having", "order by", "limit")
STAGE_ROWS = 8


def _cuts(sql):
    """Top-level positions of each clause keyword, outside strings and parens."""
    low = sql.lower()
    depth = 0
    quote = ""
    found = {}
    i = 0
    while i < len(low):
        c = low[i]
        if quote:
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            for w in _STAGE_WORDS:
                if low.startswith(w, i) and w not in found:
                    before = low[i - 1] if i else " "
                    after = low[i + len(w)] if i + len(w) < len(low) else " "
                    if not before.isalnum() and not after.isalnum():
                        found[w] = i
                        i += len(w) - 1
                        break
        i += 1
    return found


_STAGE_LABEL = {
    "raw": ("Everything, before any filtering",
            "The rows FROM and JOIN collected. Nothing has been thrown away."),
    "where": ("After WHERE",
              "Rows that failed the condition are gone. This happens before "
              "any grouping, which is why WHERE cannot see a SUM or a COUNT."),
    "group by": ("After GROUP BY",
                 "Rows sharing a value have been folded into one row each. "
                 "The individual rows no longer exist to be asked about."),
    "having": ("After HAVING",
               "Now whole groups are dropped. This is the only stage where a "
               "COUNT or SUM can be tested, because until GROUP BY ran there "
               "were no groups to test."),
    "final": ("What came back",
              "The columns you asked for, in the order you asked for them."),
}


def pipeline(sql):
    """The real rows at each stage of this query. Empty list if it has none."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql or not re.match(r"^\s*select\b", sql, re.I):
        return []
    cuts = _cuts(sql)
    fm = re.search(r"\bfrom\b", sql, re.I)
    if not fm:
        return []

    # Each stage is the FROM onwards, cut just before the next clause, with
    # the select list replaced by * so the rows show as they really are.
    #
    # Every clause is a boundary, including the ones that get no stage of
    # their own. ORDER BY was not, at first, so the HAVING fragment still
    # carried "ORDER BY spend" — and spend is an alias from the select list
    # that SELECT * does not define, so the stage failed to run and silently
    # vanished from exactly the queries it was most needed on.
    present = sorted((p, w) for w, p in cuts.items())
    marks = [("raw", present[0][0] if present else len(sql))]
    for n, (pos, w) in enumerate(present):
        end = present[n + 1][0] if n + 1 < len(present) else len(sql)
        marks.append((w, end))

    stages = []
    for key, end in marks:
        if key not in _STAGE_LABEL:
            continue
        frag = "SELECT * " + sql[fm.start():end].strip()
        r = run(frag, STAGE_ROWS)
        if not r["ok"]:
            continue
        label, note = _STAGE_LABEL[key]
        stages.append({"key": key, "label": label, "note": note,
                       "columns": r["columns"], "rows": r["rows"],
                       "count": _count(frag), "shown": r["count"]})

    final = run(sql, STAGE_ROWS)
    if final["ok"]:
        label, note = _STAGE_LABEL["final"]
        stages.append({"key": "final", "label": label, "note": note,
                       "columns": final["columns"], "rows": final["rows"],
                       "count": _count(sql), "shown": final["count"]})

    # The pipeline exists to show clauses acting on rows, so a query with no
    # clauses has nothing to show. Without this, SELECT * FROM customers
    # produced two stages holding the identical ten rows under two headings,
    # which is not a lesson about anything.
    if not any(s["key"] not in ("raw", "final") for s in stages):
        return []
    return stages if len(stages) >= 2 else []


def _count(frag):
    """How many rows that stage really had, past the display limit."""
    conn = _connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM (" + frag + ")").fetchone()[0]
    except sqlite3.Error:
        return None
    except Exception:
        return None
    finally:
        conn.close()


def schema():
    """The shape of the database, for the panel beside the editor."""
    conn = _connect()
    try:
        out = []
        for t in TABLES:
            cur = conn.execute(f"SELECT * FROM {t} LIMIT 0")
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            out.append({"table": t,
                        "columns": [d[0] for d in cur.description],
                        "rows": n})
        return out
    finally:
        conn.close()
