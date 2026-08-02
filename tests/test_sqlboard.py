"""The SQL board: the sandbox holds, the marker is fair, the path adapts.

No server and no database here — the engine is deliberately a pure module, so
this suite runs in under a second and can be run on every save.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlboard as E
import sqlcourse as C

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        fail += 1
        print(f"  FAIL  {name}" + (f"  ({detail})" if detail else ""))


# --------------------------------------------------------------------------
print("THE SANDBOX IS READ-ONLY")
# Each of these is a real attempt to change or escape the database. The point
# is not that we reject the text — it is that SQLite itself refuses, so a
# phrasing nobody thought of is refused too.
for sql in (
    "DROP TABLE customers",
    "DELETE FROM customers",
    "UPDATE products SET price = 0",
    "INSERT INTO customers VALUES (99,'x','y','z')",
    "CREATE TABLE evil (a)",
    "ALTER TABLE customers ADD COLUMN pwned TEXT",
    "ATTACH DATABASE 'vidyapath.db' AS stolen",
    "PRAGMA table_list",
    "CREATE TRIGGER t AFTER INSERT ON orders BEGIN SELECT 1; END",
    "SELECT load_extension('evil.so')",
):
    r = E.run(sql)
    check(f"refused: {sql[:38]}", not r["ok"], r.get("error", "")[:40])

# The database is rebuilt per call, so even if something did land it would not
# survive to the next request.
E.run("SELECT 1")
check("customers table is intact",
      E.run("SELECT COUNT(*) FROM customers")["rows"][0][0] == len(E.CUSTOMERS))

check("two statements at once are refused",
      not E.run("SELECT 1; DROP TABLE orders")["ok"])
check("an over-long query is refused",
      not E.run("SELECT " + "1," * 3000 + "1")["ok"])
check("an empty query is refused", not E.run("   ")["ok"])

# A runaway query has to stop by itself, or one bored student takes the box
# down for everyone.
runaway = E.run("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r)"
                " SELECT COUNT(*) FROM r")
check("a runaway recursive query is stopped", not runaway["ok"],
      runaway.get("error", "")[:44])

# --------------------------------------------------------------------------
print("\nREADING WORKS")
r = E.run("SELECT name, city FROM customers WHERE city = 'Bengaluru'")
check("a plain SELECT runs", r["ok"] and r["count"] == 2, str(r.get("count")))
check("columns come back named", r.get("columns") == ["name", "city"])
check("timing is reported", isinstance(r.get("ms"), float))

big = E.run("SELECT a.id FROM orders a, orders b, orders c")
check("a cartesian product is truncated, not fatal",
      big["ok"] and big["truncated"] and big["count"] == E.MAX_ROWS,
      f"{big['count']} rows shown")

check("the schema panel lists four tables", len(E.schema()) == 4)

# --------------------------------------------------------------------------
print("\nERRORS SAY SOMETHING USEFUL")
cases = [
    ("SELECT cust_id FROM orders", "no column called"),
    ("SELECT * FROM custmers", "no table called"),
    ("SELECT id FROM customers c JOIN orders o ON o.customer_id = c.id",
     "cannot tell which one"),
    ("SELECT * FORM customers", "stopped at"),
    ("SELECT name FROM customers WHERE", "stops in the middle"),
    ("SELECT city FROM customers WHERE COUNT(*) > 1", "HAVING"),
]
for sql, want in cases:
    r = E.run(sql)
    check(f"explains: {sql[:34]}", (not r["ok"]) and want in r["error"],
          r.get("error", "")[:52])

# --------------------------------------------------------------------------
print("\nTHE PLAN IS REAL")
p = E.plan("SELECT id FROM orders WHERE customer_id = 5")
check("a plan comes back", p["ok"] and len(p["steps"]) >= 1,
      "; ".join(p.get("steps", []))[:60])
check("a full scan is named as one", "SCAN" in " ".join(p["steps"]))
check("the primary key is used when you look one up",
      "SEARCH" in " ".join(E.plan("SELECT * FROM customers WHERE id = 3")["steps"]))
check("a broken query has no plan", not E.plan("SELECT FROM")["ok"])

# --------------------------------------------------------------------------
print("\nTHE JOIN PICTURE MATCHES THE DATA")
t = E.join_trace("customers", "id", "orders", "customer_id")
check("the trace builds", t["ok"])
check("every pair is a real match",
      all(t["left"]["rows"][a][0] == t["right"]["rows"][b][1]
          for a, b in t["pairs"]),
      f"{len(t['pairs'])} pairs")
check("the pair count equals what an INNER JOIN returns",
      len(t["pairs"]) == E.run("SELECT c.id FROM customers c "
                               "JOIN orders o ON o.customer_id = c.id")["count"])
# The three buyers-of-nothing are the whole reason this database exists.
lonely = {t["left"]["rows"][i][1] for i in t["unmatched_left"]}
check("the customers who never ordered are found",
      lonely == {"Priya Nair", "Sam Fernandes", "Nadia Khan"}, str(sorted(lonely)))
check("an unknown table is refused", not E.join_trace("secrets", "id",
                                                     "orders", "id")["ok"])
check("an unknown column is refused", not E.join_trace("customers", "nope",
                                                       "orders", "id")["ok"])

# --------------------------------------------------------------------------
print("\nEVERY EXERCISE IS SOUND")
ids = [x["id"] for x in C.EXERCISES]
check("ids are unique", len(set(ids)) == len(ids))
check("every skill has at least one exercise",
      all(C.BY_SKILL.get(s) for s, _ in C.SKILLS),
      str([s for s, _ in C.SKILLS if not C.BY_SKILL.get(s)]))
bad = []
for x in C.EXERCISES:
    r = E.run(x["ref"])
    if not r["ok"] or r["count"] == 0:
        bad.append((x["id"], r.get("error", "no rows")[:50]))
check("every model answer runs and returns rows", not bad, str(bad))
check("the answer is never sent to the page",
      "ref" not in C.public(C.EXERCISES[0]))

# --------------------------------------------------------------------------
print("\nMARKING IS ABOUT ROWS, NOT SPELLING")
e7 = C.BY_ID["e7"]
# Different text, same rows: an older JOIN syntax and different aliases.
alt = ("SELECT customers.name, orders.id FROM customers, orders "
       "WHERE orders.customer_id = customers.id")
check("a differently-written correct query passes", C.mark(e7, alt)["correct"])
check("the model answer passes its own marking", C.mark(e7, e7["ref"])["correct"])

e3 = C.BY_ID["e3"]
m = C.mark(e3, "SELECT title, price FROM products ORDER BY price LIMIT 3")
check("right rows in the wrong order is caught", not m["correct"])
m = C.mark(e3, "SELECT title, price FROM products ORDER BY price DESC LIMIT 5")
check("too many rows is named as too many", not m["correct"] and
      "plus 2 more" in m["why"], m["why"][:60])

e1 = C.BY_ID["e1"]
m = C.mark(e1, "SELECT name FROM customers WHERE city = 'Bengaluru'")
check("a missing column is named", not m["correct"] and
      "1 column" in m["why"], m["why"][:60])
m = C.mark(e1, "SELECT nam, city FROM customers")
check("a broken query is marked as an error, not as wrong",
      m["state"] == "error" and "no column called" in m["why"])
check("the rows are shown even when the answer is wrong",
      C.mark(e1, "SELECT name, city FROM customers")["result"]["ok"])

e8 = C.BY_ID["e8"]
m = C.mark(e8, "SELECT c.name FROM customers c JOIN orders o "
               "ON o.customer_id = c.id WHERE o.id IS NULL")
check("INNER where OUTER was needed is caught", not m["correct"])
m = C.mark(e8, e8["ref"])
check("LEFT JOIN plus IS NULL is recognised in the praise",
      m["correct"] and "LEFT JOIN" in m["why"])

# --------------------------------------------------------------------------
print("\nTHE PATH FOLLOWS THE STUDENT")
check("with no history it starts at the beginning",
      C.next_up({})["skill"] == "select")
hist = {x["id"]: {"tries": 1, "solved": True} for x in C.EXERCISES}
check("with everything solved there is nothing next", C.next_up(hist) is None)

hist = {"e1": {"tries": 3, "solved": False}}
check("an unsolved attempt is offered again, not skipped",
      C.next_up(hist)["id"] == "e1")

hist = {"e1": {"tries": 1, "solved": True}}
nxt = C.next_up(hist)
check("solving one moves you on", nxt["id"] != "e1", nxt["id"])

pr = C.progress({"e1": {"tries": 2, "solved": True}})
sel = [p for p in pr if p["skill"] == "select"][0]
check("progress counts what was solved", sel["done"] == 1 and sel["tries"] == 2)
check("progress covers every skill", len(pr) == len(C.SKILLS))

# --------------------------------------------------------------------------
print("\nTHE PIPELINE IS THE REAL ROWS")
FULL = ("SELECT c.name, SUM(i.qty*p.price) AS spend FROM customers c "
        "JOIN orders o ON o.customer_id=c.id "
        "JOIN order_items i ON i.order_id=o.id "
        "JOIN products p ON p.id=i.product_id WHERE o.status='completed' "
        "GROUP BY c.id HAVING SUM(i.qty*p.price)>5000 ORDER BY spend DESC")
st = E.pipeline(FULL)
keys = [s["key"] for s in st]
check("every clause gets a stage",
      keys == ["raw", "where", "group by", "having", "final"], str(keys))
check("rows only ever fall through the pipeline",
      all(st[i]["count"] >= st[i + 1]["count"] for i in range(len(st) - 1)),
      str([s["count"] for s in st]))
check("the last stage matches simply running the query",
      st[-1]["count"] == E.run(FULL)["count"])
# An ORDER BY on a select-list alias used to break the HAVING fragment, which
# removed the stage from exactly the queries that needed it most.
check("an ORDER BY on an alias does not eat a stage", "having" in keys)

check("a subquery is not mistaken for a clause boundary",
      [s["key"] for s in E.pipeline(
          "SELECT title FROM products WHERE price > "
          "(SELECT AVG(price) FROM products)")] == ["raw", "where", "final"])
check("a WHERE inside a string is not a clause",
      [s["key"] for s in E.pipeline(
          "SELECT name FROM customers WHERE city = 'group by where'")]
      == ["raw", "where", "final"])
check("a query with no stages to show returns none",
      E.pipeline("SELECT * FROM customers") == [])
check("a broken query has no pipeline", E.pipeline("SELECT FROM") == [])
check("a non-SELECT has no pipeline", E.pipeline("DROP TABLE customers") == [])
check("stages are capped for display",
      all(s["shown"] <= E.STAGE_ROWS for s in st),
      str([s["shown"] for s in st]))

print("\nTHE WALKTHROUGH READS THE QUERY")
w = E.walkthrough(FULL, E.run(FULL))
check("it names every clause in execution order",
      [s["key"] for s in w["steps"]] ==
      ["from", "where", "group", "having", "select", "order"],
      str([s["key"] for s in w["steps"]]))
check("it counts the real base tables",
      "customers (10 rows)" in w["steps"][0]["note"])
check("an inner join is called out", "inner join" in w["steps"][0]["note"])
check("a left join is called out differently",
      "LEFT JOIN" in E.walkthrough(
          "SELECT c.name FROM customers c LEFT JOIN orders o "
          "ON o.customer_id=c.id")["steps"][0]["note"])
check("a cross join is warned about",
      any("cross join" in n for n in
          E.walkthrough("SELECT * FROM customers, orders")["notes"]))
check("a window function is noticed",
      any("window function" in n for n in E.walkthrough(
          "SELECT title, RANK() OVER (ORDER BY price) FROM products")["notes"]))
check("an empty query has no walkthrough", not E.walkthrough("")["ok"])

# --------------------------------------------------------------------------
print("\nIT GOES PAST BEGINNER")
adv = [x for x in C.EXERCISES if x["id"].startswith("x")]
check("there are expert exercises at all", len(adv) >= 12, str(len(adv)))
check("every skill has at least one exercise, expert ones included",
      all(C.BY_SKILL.get(s) for s, _ in C.SKILLS),
      str([s for s, _ in C.SKILLS if not C.BY_SKILL.get(s)]))
# The things somebody is actually paid to know.
for skill in ("sets", "cte", "frames", "dedup", "shape", "recursive"):
    check(f"{skill} is covered", bool(C.BY_SKILL.get(skill)))
check("the beginner path still starts at the beginning",
      C.next_up({})["skill"] == "select")
check("expert questions come after the basics",
      C.ORDER.index("recursive") > C.ORDER.index("select"))

# A recursive CTE is one of the things an expert most needs to practise, and
# the authorizer was refusing every one of them: SQLite asks permission to
# read the CTE's own name, which is not one of the four tables.
r = E.run("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n "
          "WHERE i < 5) SELECT COUNT(*) FROM n")
check("recursive CTEs run", r["ok"] and r["rows"][0][0] == 5,
      r.get("error", "")[:40])
check("plain CTEs run", E.run("WITH t AS (SELECT 1 x) SELECT x FROM t")["ok"])
check("window frames run",
      E.run("SELECT SUM(qty) OVER (ORDER BY id) FROM order_items")["ok"])
check("FILTER runs",
      E.run("SELECT COUNT(*) FILTER (WHERE status='completed') FROM orders")["ok"])
check("set operations run",
      E.run("SELECT id FROM customers EXCEPT SELECT customer_id FROM orders")["ok"])
# ...and none of that reopened the schema tables.
for t in ("sqlite_master", "sqlite_sequence", "SQLITE_MASTER"):
    check(f"{t} is still refused", not E.run(f"SELECT * FROM {t}")["ok"])
check("a runaway recursion is still stopped",
      not E.run("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r)"
                " SELECT COUNT(*) FROM r")["ok"])
check("writes are still refused", not E.run("DROP TABLE customers")["ok"])

# The anti-join exercise needs something that was never ordered, or its
# answer is an empty table and it teaches nothing.
check("the catalogue has dead stock to find",
      E.run("SELECT p.id FROM products p WHERE NOT EXISTS "
            "(SELECT 1 FROM order_items i WHERE i.product_id = p.id)"
            )["count"] >= 1)

print(f"\nPASSED {ok}   FAILED {fail}")
sys.exit(1 if fail else 0)
