"""The SQL board's exercises, marking and what to give someone next.

Marking is done by running both queries and comparing the rows that come back,
not by comparing the text. There is no single correct way to write a query,
and a marker that insists on one teaches people to type from memory. If your
query returns the right rows, it is right — and if it returns nearly the right
rows, this says which ones are missing rather than "incorrect".

Choosing the next exercise is arithmetic over what the student has already
got wrong. No model call: what to practise next is a decision about their
history, and their history is sitting in the database. Sending it to a
language model to be told "revise JOINs" would cost money to be told something
a comparison already knows.
"""
import re

import sqlboard as E

# --------------------------------------------------------------------------
# Skills. The adaptive path moves between these, not between exercises, so a
# student who keeps failing GROUP BY is given a different GROUP BY question
# rather than being marched forward on schedule.
# --------------------------------------------------------------------------
SKILLS = [
    ("select", "Picking columns and rows"),
    ("order", "Sorting and limiting"),
    ("aggregate", "Counting and totalling"),
    ("group", "Grouping, and filtering groups"),
    ("join", "Joining two tables"),
    ("outer", "Keeping the rows that do not match"),
    ("multi", "Joining three or more tables"),
    ("subquery", "Queries inside queries"),
    ("window", "Window functions"),
    ("perf", "Indexes and query plans"),
]
SKILL_NAME = dict(SKILLS)
ORDER = [s for s, _ in SKILLS]


def _q(*lines):
    return "\n".join(lines)


# Every exercise carries the reference query, not a reference string: the
# marker runs it. `visual` opts an exercise into the JOIN picture.
EXERCISES = [
    dict(id="e1", skill="select", title="Customers in one city",
         ask="List the name and city of every customer in Bengaluru.",
         hint="WHERE compares a column to a value. Text goes in single quotes.",
         ref=_q("SELECT name, city FROM customers WHERE city = 'Bengaluru'")),

    dict(id="e2", skill="select", title="Cheap enough to not think about",
         ask="Show the title and price of every product under 2000, "
             "cheapest first.",
         hint="WHERE for the filter, ORDER BY for the sort.",
         ref=_q("SELECT title, price FROM products",
                "WHERE price < 2000 ORDER BY price")),

    dict(id="e3", skill="order", title="The three priciest things",
         ask="Show the three most expensive products, dearest first, with "
             "their title and price.",
         hint="ORDER BY ... DESC puts the largest first. LIMIT cuts the list.",
         ref=_q("SELECT title, price FROM products",
                "ORDER BY price DESC LIMIT 3")),

    dict(id="e4", skill="aggregate", title="How many, and how much",
         ask="In one row, return how many products there are as `n` and their "
             "average price as `avg_price`.",
         hint="COUNT(*) and AVG(price), with AS to name each one.",
         ref=_q("SELECT COUNT(*) AS n, AVG(price) AS avg_price FROM products")),

    dict(id="e5", skill="group", title="One row per category",
         ask="For each product category, return the category and how many "
             "products it has as `n`.",
         hint="GROUP BY collapses rows that share a value into one row each.",
         ref=_q("SELECT category, COUNT(*) AS n FROM products",
                "GROUP BY category")),

    dict(id="e6", skill="group", title="Only the busy cities",
         ask="Return each city that has more than one customer, with the "
             "count as `n`.",
         hint="WHERE filters rows before grouping. To filter the groups "
              "themselves you need HAVING.",
         ref=_q("SELECT city, COUNT(*) AS n FROM customers",
                "GROUP BY city HAVING COUNT(*) > 1")),

    dict(id="e7", skill="join", title="Who placed which order",
         ask="For every order, return the customer's name and the order's id. "
             "Only orders that belong to a customer.",
         hint="JOIN orders to customers on orders.customer_id = customers.id.",
         visual=dict(left="customers", left_key="id",
                     right="orders", right_key="customer_id"),
         ref=_q("SELECT c.name, o.id FROM customers c",
                "JOIN orders o ON o.customer_id = c.id")),

    dict(id="e8", skill="outer", title="The customers who never bought",
         ask="Return the name of every customer who has never placed an "
             "order.",
         hint="LEFT JOIN keeps customers with no match and fills the order "
              "columns with NULL. Then keep only those NULL rows.",
         visual=dict(left="customers", left_key="id",
                     right="orders", right_key="customer_id"),
         ref=_q("SELECT c.name FROM customers c",
                "LEFT JOIN orders o ON o.customer_id = c.id",
                "WHERE o.id IS NULL")),

    dict(id="e9", skill="multi", title="What was in the basket",
         ask="For every completed order, return the customer's name and the "
             "product title of each item in it.",
         hint="Four tables: customers to orders to order_items to products.",
         ref=_q("SELECT c.name, p.title",
                "FROM orders o",
                "JOIN customers c ON c.id = o.customer_id",
                "JOIN order_items i ON i.order_id = o.id",
                "JOIN products p ON p.id = i.product_id",
                "WHERE o.status = 'completed'")),

    dict(id="e10", skill="multi", title="Total spend per customer",
         ask="For each customer who has spent anything on completed orders, "
             "return their name and their total spend as `spend`, biggest "
             "first. Spend is quantity times price.",
         hint="SUM(i.qty * p.price), grouped by the customer.",
         ref=_q("SELECT c.name, SUM(i.qty * p.price) AS spend",
                "FROM customers c",
                "JOIN orders o ON o.customer_id = c.id",
                "JOIN order_items i ON i.order_id = o.id",
                "JOIN products p ON p.id = i.product_id",
                "WHERE o.status = 'completed'",
                "GROUP BY c.id ORDER BY spend DESC")),

    dict(id="e11", skill="subquery", title="Dearer than average",
         ask="Return the title and price of every product priced above the "
             "average price of all products.",
         hint="The inner query works out the average; the outer one compares "
              "against it.",
         ref=_q("SELECT title, price FROM products",
                "WHERE price > (SELECT AVG(price) FROM products)")),

    dict(id="e12", skill="window", title="Ranked without collapsing",
         ask="Return every product's title, category and price, plus its "
             "position within its own category by price, dearest first, as "
             "`rank_in_cat`.",
         hint="RANK() OVER (PARTITION BY category ORDER BY price DESC). A "
              "window function ranks rows without folding them together the "
              "way GROUP BY does.",
         ref=_q("SELECT title, category, price,",
                "  RANK() OVER (PARTITION BY category ORDER BY price DESC)",
                "    AS rank_in_cat",
                "FROM products")),

    dict(id="e13", skill="perf", title="Read the plan",
         ask="Write the query that finds the orders belonging to customer 5, "
             "returning the order id and status. Then open the plan tab and "
             "read what SQLite did to find them.",
         hint="A plain WHERE on customer_id. The plan is the lesson here, not "
              "the query.",
         plan_focus=True,
         ref=_q("SELECT id, status FROM orders WHERE customer_id = 5")),
]

BY_ID = {x["id"]: x for x in EXERCISES}
BY_SKILL = {}
for _x in EXERCISES:
    BY_SKILL.setdefault(_x["skill"], []).append(_x)


def public(ex):
    """An exercise as the page is allowed to see it — without the answer."""
    return {"id": ex["id"], "skill": ex["skill"],
            "skill_name": SKILL_NAME.get(ex["skill"], ex["skill"]),
            "title": ex["title"], "ask": ex["ask"], "hint": ex["hint"],
            "visual": ex.get("visual"), "plan_focus": ex.get("plan_focus", False)}


# --------------------------------------------------------------------------
# Marking
# --------------------------------------------------------------------------
_ORDERED = re.compile(r"\border\s+by\b", re.I)
_AGG_ONLY = re.compile(r"\b(select|from|where|group|having|order|join|limit)\b", re.I)


def _norm(rows):
    """Rows as comparable tuples. Floats are rounded because 4500.000000001
    and 4500.0 are the same answer, and a marker that disagrees is broken."""
    out = []
    for r in rows:
        out.append(tuple(round(v, 4) if isinstance(v, float) else v for v in r))
    return out


def mark(ex, sql):
    """Run the student's query beside the reference and compare the rows.

    Returns the same shape whether they were right or wrong, because the page
    shows the result table either way — being wrong is not a reason to hide
    what your query actually did.
    """
    got = E.run(sql)
    if not got["ok"]:
        return {"correct": False, "state": "error", "result": got,
                "why": got["error"]}

    want = E.run(ex["ref"])
    ordered = bool(_ORDERED.search(ex["ref"]))
    g, w = _norm(got["rows"]), _norm(want["rows"])

    if not ordered:
        g_cmp, w_cmp = sorted(g, key=repr), sorted(w, key=repr)
    else:
        g_cmp, w_cmp = g, w

    if g_cmp == w_cmp:
        return {"correct": True, "state": "correct", "result": got,
                "why": _praise(sql, ex), "expected_count": len(w)}

    # Wrong. Say how, precisely — "incorrect" is the least useful thing a
    # marker can say, and every one of these differences names the mistake.
    ncols_g = len(got["columns"])
    ncols_w = len(want["columns"])
    if ncols_g != ncols_w:
        why = (f"Your query returns {ncols_g} column"
               f"{'' if ncols_g == 1 else 's'}, and the question asks for "
               f"{ncols_w}. Check the list after SELECT.")
    elif ordered and sorted(g, key=repr) == sorted(w, key=repr):
        why = ("You have exactly the right rows, in the wrong order. The "
               "question fixes an order, so this one needs ORDER BY.")
    elif len(g) > len(w) and set(w) <= set(g):
        extra = len(g) - len(w)
        why = (f"You have every row that was wanted, plus {extra} more. "
               f"Something needs filtering out — check the WHERE, or whether "
               f"a JOIN is multiplying rows.")
    elif len(g) < len(w) and set(g) <= set(w):
        miss = len(w) - len(g)
        why = (f"{miss} row{'' if miss == 1 else 's'} are missing. A filter is "
               f"too strict, or an INNER JOIN has dropped the rows that did "
               f"not match.")
    else:
        why = (f"That returns {len(g)} row{'' if len(g) == 1 else 's'} and the "
               f"answer has {len(w)}. Run it and read the first few rows "
               f"against the question — they usually disagree in an obvious "
               f"way once you look.")
    return {"correct": False, "state": "wrong", "result": got, "why": why,
            "expected_count": len(w)}


def _praise(sql, ex):
    """Correct, and occasionally worth a word about how.

    Only where the observation is a fact about their text, so it is never
    wrong and never flattery."""
    s = sql.lower()
    if ex["skill"] == "outer" and "left join" in s:
        return ("Correct. The LEFT JOIN plus IS NULL is the standard way to "
                "ask 'which of these has none of those' — it comes up in "
                "interviews more than any other pattern.")
    if ex["skill"] == "group" and "having" in s:
        return ("Correct, and you used HAVING rather than trying to put the "
                "count in WHERE. That ordering — filter rows, group, filter "
                "groups — is the thing the question was testing.")
    if "select *" in s:
        return ("Right rows. One habit worth breaking early: SELECT * ships "
                "every column over the wire and breaks silently when someone "
                "adds one. Name the columns you want.")
    return "Correct."


# --------------------------------------------------------------------------
# What to do next
# --------------------------------------------------------------------------
def next_up(history):
    """Pick the next exercise from what has already happened.

    `history` is {exercise_id: {"tries": n, "solved": bool}}.

    The rule, in order: anything solved is done; a skill you got wrong is
    worth another question of the same skill before moving on; otherwise walk
    forward. Deliberately boring, entirely predictable, and free.
    """
    hist = history or {}

    def solved(x):
        return bool(hist.get(x["id"], {}).get("solved"))

    unsolved = [x for x in EXERCISES if not solved(x)]
    if not unsolved:
        return None

    # A skill with a failed attempt outranks the running order: being moved on
    # from something you just got wrong is how people end up with holes.
    shaky = [x for x in unsolved
             if hist.get(x["id"], {}).get("tries") and not solved(x)]
    if shaky:
        return shaky[0]

    weak = {x["skill"] for x in EXERCISES
            if hist.get(x["id"], {}).get("tries", 0) >= 2 and not solved(x)}
    for s in ORDER:
        if s in weak:
            same = [x for x in unsolved if x["skill"] == s]
            if same:
                return same[0]

    for s in ORDER:
        same = [x for x in unsolved if x["skill"] == s]
        if same:
            return same[0]
    return unsolved[0]


def progress(history):
    """Per-skill counts, for the bar down the side of the board."""
    hist = history or {}
    out = []
    for sid, name in SKILLS:
        xs = BY_SKILL.get(sid, [])
        done = sum(1 for x in xs if hist.get(x["id"], {}).get("solved"))
        tries = sum(hist.get(x["id"], {}).get("tries", 0) for x in xs)
        out.append({"skill": sid, "name": name, "total": len(xs),
                    "done": done, "tries": tries})
    return out
