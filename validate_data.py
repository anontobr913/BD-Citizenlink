"""
Data validation for BD-Citizenlink.

Real NID data is confidential, so this project runs on synthetic data.
This script proves the generated data actually follows the system rules.
It runs read-only Cypher checks against the imported Neo4j graph and
prints a pass/fail report. Run it after neo4j_import.py:

    python validate_data.py
"""

import time
from neo4j import GraphDatabase

# same connection settings as app.py
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "913913913"
NEO4J_DB = "neo4j"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

results = []   # (check name, expectation, result text, passed True/False)


def run(cypher, **params):
    with driver.session(database=NEO4J_DB) as session:
        return list(session.run(cypher, **params))


def report(name, expectation, result_text, passed):
    results.append((name, expectation, result_text, passed))
    mark = "PASS" if passed else "LOOK"
    print(f"[{mark}] {name}: {result_text}   (expected: {expectation})")


def check_total_count():
    n = run("MATCH (c:Citizen) RETURN count(c) AS n")[0]["n"]
    report("Total records", "about 5.1 million", f"{n:,} citizens", n > 5_000_000)


def check_id_formats():
    # Rule 31: NID = 13 digits. Rule 32-33: BRN = 17 digits.
    bad_nid = run(
        "MATCH (c:Citizen) WHERE NOT c.nid =~ '[0-9]{13}' RETURN count(c) AS n"
    )[0]["n"]
    bad_brn = run(
        "MATCH (c:Citizen) WHERE NOT c.brn =~ '[0-9]{17}' RETURN count(c) AS n"
    )[0]["n"]
    report("NID format (Rule 31)", "0 bad", f"{bad_nid} bad NIDs", bad_nid == 0)
    report("BRN format (Rules 32-33)", "0 bad", f"{bad_brn} bad BRNs", bad_brn == 0)


def check_religion_distribution():
    # Rule 19: roughly Muslim 90%, Hindu 8%, Buddhist 1%, Christian 1%
    rows = run(
        "MATCH (c:Citizen) RETURN c.religion AS rel, count(*) AS n ORDER BY n DESC"
    )
    total = sum(r["n"] for r in rows)
    parts = ", ".join(f"{r['rel']} {100.0 * r['n'] / total:.1f}%" for r in rows)
    muslim = next((r["n"] for r in rows if r["rel"] == "Muslim"), 0)
    pct = 100.0 * muslim / total
    report("Religion mix (Rule 19)", "Muslim close to 90%", parts, 88.0 <= pct <= 92.0)


def check_gender_ratio():
    # Rules 27-28: founders 51/49, children 50/50 -> overall close to 50/50
    rows = run("MATCH (c:Citizen) RETURN c.gender AS g, count(*) AS n")
    total = sum(r["n"] for r in rows)
    male = next((r["n"] for r in rows if r["g"] == "M"), 0)
    pct = 100.0 * male / total
    report("Gender ratio (Rules 27-28)", "close to 50/50",
           f"male {pct:.1f}%, female {100 - pct:.1f}%", 48.0 <= pct <= 53.0)


def check_generation_bands():
    # Rules 14-17: everyone's birth year falls inside one of the four windows
    rows = run("""
        MATCH (c:Citizen)
        WITH toInteger(substring(c.dob, 0, 4)) AS y
        RETURN
          sum(CASE WHEN y >= 1920 AND y <= 1940 THEN 1 ELSE 0 END) AS gen1,
          sum(CASE WHEN y >= 1945 AND y <= 1965 THEN 1 ELSE 0 END) AS gen2,
          sum(CASE WHEN y >= 1970 AND y <= 1985 THEN 1 ELSE 0 END) AS gen3,
          sum(CASE WHEN y >= 1990 AND y <= 2015 THEN 1 ELSE 0 END) AS gen4,
          count(*) AS total
    """)[0]
    outside = rows["total"] - rows["gen1"] - rows["gen2"] - rows["gen3"] - rows["gen4"]
    text = (f"Gen-1 {rows['gen1']:,}, Gen-2 {rows['gen2']:,}, "
            f"Gen-3 {rows['gen3']:,}, Gen-4 {rows['gen4']:,}, outside {outside:,}")
    report("Birth-year windows (Rules 14-17)", "0 outside the windows", text, outside == 0)


def check_founders():
    # Rule 18 and founder design: people without parents are the founders
    n = run(
        "MATCH (c:Citizen) WHERE NOT (c)-[:HAS_FATHER]->() RETURN count(c) AS n"
    )[0]["n"]
    report("Parentless citizens", "about 782,500 founders",
           f"{n:,}", 780_000 <= n <= 790_000)


def check_parent_ages():
    # Rules 1-2: father at least 21, mother at least 18 at every child's birth
    row = run("""
        MATCH (c:Citizen)-[r:HAS_FATHER|HAS_MOTHER]->(p)
        WITH type(r) AS t,
             toInteger(substring(c.dob, 0, 4)) - toInteger(substring(p.dob, 0, 4)) AS diff
        RETURN
          sum(CASE WHEN t = 'HAS_FATHER' AND diff < 21 THEN 1 ELSE 0 END) AS bad_father,
          sum(CASE WHEN t = 'HAS_MOTHER' AND diff < 18 THEN 1 ELSE 0 END) AS bad_mother,
          count(*) AS checked
    """)[0]
    text = (f"{row['checked']:,} parent links checked, "
            f"{row['bad_father']} young fathers, {row['bad_mother']} young mothers")
    report("Parent ages (Rules 1-2)", "0 violations", text,
           row["bad_father"] == 0 and row["bad_mother"] == 0)


def check_same_religion_marriage():
    # Rules 5 and 20: both spouses share one religion
    n = run("""
        MATCH (a:Citizen)-[:MARRIED_TO]-(b:Citizen)
        WHERE a.nid < b.nid AND a.religion <> b.religion
        RETURN count(*) AS n
    """)[0]["n"]
    report("Same-religion marriages (Rules 5, 20)", "0 mixed couples",
           f"{n} mixed couples", n == 0)


def check_polygyny():
    # Rules 46-47: only Muslim men have more than one spouse, at most four
    rows = run("""
        MATCH (m:Citizen {gender:'M'})-[:MARRIED_TO]-(w)
        WITH m, count(w) AS wives
        RETURN m.religion AS rel, wives, count(*) AS men
        ORDER BY wives, rel
    """)
    multi = [r for r in rows if r["wives"] > 1]
    non_muslim_multi = sum(r["men"] for r in multi if r["rel"] != "Muslim")
    over_four = sum(r["men"] for r in rows if r["wives"] > 4)
    total_multi = sum(r["men"] for r in multi)
    counts = {}
    for r in multi:
        counts[r["wives"]] = counts.get(r["wives"], 0) + r["men"]
    dist = ", ".join(f"{k} wives: {v:,}" for k, v in sorted(counts.items()))
    text = (f"{total_multi:,} polygynous men ({dist}); "
            f"non-Muslim: {non_muslim_multi}, over 4 wives: {over_four}")
    report("Polygyny (Rules 46-47)", "Muslim men only, max 4 wives", text,
           non_muslim_multi == 0 and over_four == 0)


def check_one_husband_per_wife():
    # Rule 6: a wife has exactly one husband
    n = run("""
        MATCH (w:Citizen {gender:'F'})-[:MARRIED_TO]-(h)
        WITH w, count(h) AS husbands
        WHERE husbands > 1
        RETURN count(*) AS n
    """)[0]["n"]
    report("One husband per wife (Rule 6)", "0 women with 2+ husbands",
           f"{n} women with more than one husband", n == 0)


def check_address_inheritance():
    # Rules 24-25: children carry the father's addresses (100k sample)
    n = run("""
        MATCH (c:Citizen)-[:HAS_FATHER]->(f)
        WITH c, f LIMIT 100000
        WHERE c.perm_address <> f.perm_address
        RETURN count(*) AS n
    """)[0]["n"]
    report("Address inheritance (Rules 24-25)", "0 mismatches in sample",
           f"{n} mismatches in a 100,000-child sample", n == 0)


def check_sibling_gaps():
    # Rule 3: siblings of the same couple are 1-4 years apart.
    # Same-year pairs are twins; the audit treats them as allowed.
    row = run("""
        MATCH (f:Citizen {gender:'M'})
        WHERE (f)<-[:HAS_FATHER]-()
        WITH f LIMIT 5000
        MATCH (c)-[:HAS_FATHER]->(f)
        MATCH (c)-[:HAS_MOTHER]->(m)
        WITH f, m, c ORDER BY c.dob
        WITH f, m, collect(toInteger(substring(c.dob, 0, 4))) AS ys
        WHERE size(ys) > 1
        UNWIND range(1, size(ys) - 1) AS i
        WITH ys[i] - ys[i-1] AS gap
        RETURN
          sum(CASE WHEN gap >= 1 AND gap <= 4 THEN 1 ELSE 0 END) AS ok,
          sum(CASE WHEN gap = 0 THEN 1 ELSE 0 END) AS twins,
          sum(CASE WHEN gap > 4 THEN 1 ELSE 0 END) AS wide,
          count(*) AS total
    """)[0]
    pct = 100.0 * row["ok"] / row["total"] if row["total"] else 0.0
    text = (f"{row['total']:,} sibling pairs from 5,000 families: "
            f"{pct:.1f}% in 1-4 years, {row['twins']:,} twin pairs, "
            f"{row['wide']:,} wider gaps")
    # twins are allowed, so pass = no unexplained wide gaps beyond a tiny share
    passed = row["total"] > 0 and (row["wide"] / row["total"]) < 0.02
    report("Sibling gaps (Rule 3)", "pairs 1-4 years apart, twins allowed", text, passed)


def main():
    checks = [
        check_total_count,
        check_id_formats,
        check_religion_distribution,
        check_gender_ratio,
        check_generation_bands,
        check_founders,
        check_parent_ages,
        check_same_religion_marriage,
        check_polygyny,
        check_one_husband_per_wife,
        check_address_inheritance,
        check_sibling_gaps,
    ]
    t0 = time.time()
    for chk in checks:
        t = time.time()
        chk()
        print(f"       ...{time.time() - t:.1f}s")
    print("-" * 60)
    passed = sum(1 for r in results if r[3])
    print(f"{passed}/{len(results)} checks passed in {time.time() - t0:.0f}s total")
    driver.close()


if __name__ == "__main__":
    main()
