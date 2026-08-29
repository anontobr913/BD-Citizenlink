"""
Inject Multiple-Marriage (Polygyny) instances into an EXISTING dataset.

Why this exists
---------------
`Nid_data_create.py` now generates polygynous Muslim marriages on every fresh
run. But regenerating the full ~5.1M-row `Nid_data_create.csv` would change every
NID and force a complete Neo4j re-import. This utility instead *surgically*
upgrades a handful of already-married Muslim men in the current CSV so you can
immediately see multiple marriages in the visualization, without touching any
existing NIDs.

What it does
------------
1. Picks `NUM_HUSBANDS` existing married Muslim men (founder generation).
2. Gives each of them 1-3 *additional* wives (Islam permits up to 4 total).
3. Gives every new wife her own set of children -> these become HALF-SIBLINGS of
   the man's existing children (they share only the father).
4. Rewrites each selected man's `spouse_nid` to a pipe-separated list ("W1|W2|W3")
   and appends the new wife + child rows to the CSV.
5. Writes `polygamy_delta.csv` (only the changed/new rows) and, with `--neo4j`,
   pushes just those rows straight into Neo4j so the graph updates in seconds.

Run
---
    python inject_multiple_marriages.py            # update the CSV + write delta
    python inject_multiple_marriages.py --neo4j    # ...and push delta to Neo4j
"""

import json
import csv
import random
import os
import sys
import time

CSV_FILE   = 'Nid_data_create.csv'
DELTA_FILE = 'polygamy_delta.csv'
SPOUSE_SEP = '|'

# How aggressive the injection is (kept small so it's easy to eyeball in the app).
NUM_HUSBANDS = 25          # existing Muslim men to turn polygynous
EXTRA_WIVES  = (1, 3)      # additional wives added on top of the existing one
FOUNDER_MAX_YEAR = 1940    # only pick founder-generation husbands (clear trees)

HEADER = ["nid", "brn", "full_name", "gender", "blood_group", "dob", "religion",
          "father_name", "mother_name", "father_nid", "mother_nid", "spouse_nid",
          "perm_address", "pres_address", "is_migrated"]

BLOOD = ['A+', 'O+', 'B+', 'AB+', 'A-', 'O-', 'B-', 'AB-']


def gen_cfg(husband_year):
    """Return child-generation settings based on a husband's birth year, so the
    new children land inside a valid generation birth-year window."""
    if husband_year <= 1944:      # Founder (Gen-1) -> children are Gen-2
        return {'child_range': (1945, 1965), 'k_range': (4, 8),
                'wife_year': (1920, 1942), 'name_gen': 'gen_1_2'}
    if husband_year <= 1969:      # Gen-2 -> children are Gen-3
        return {'child_range': (1970, 1985), 'k_range': (2, 6),
                'wife_year': (1945, 1965), 'name_gen': 'gen_1_2'}
    return {                      # Gen-3 -> children are Gen-4
        'child_range': (1990, 2015), 'k_range': (1, 4),
        'wife_year': (1970, 1983), 'name_gen': 'gen_3_plus'}


def main():
    t0 = time.time()
    push_to_neo4j = '--neo4j' in sys.argv

    print("Loading name & district pools...")
    with open('districts.json', 'r') as f: geo = json.load(f)
    with open('names.json', 'r') as f: names = json.load(f)
    dcodes = geo['district_codes']

    divs = ['Dhaka', 'Chattogram', 'Rajshahi', 'Barishal', 'Khulna', 'Sylhet']
    weights = [30, 20, 15, 15, 10, 10]

    def weighted_location():
        div = random.choices(divs, weights=weights)[0]
        dist = random.choice(list(geo['divisions'][div].keys()))
        thana = random.choice(geo['divisions'][div][dist])
        return f"Holding {random.randint(1, 500)}, {thana}, {dist}, {div}", dist

    # --- Pass 1: collect existing NIDs (uniqueness) + reservoir-sample husbands ---
    print(f"Pass 1: scanning {CSV_FILE} for candidate husbands...")
    existing_nids = set()   # stored as ints to keep memory down
    husbands = []
    seen_candidates = 0

    with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            existing_nids.add(int(row[0]))
            # Candidate = Muslim, male, already married to exactly one spouse,
            # and a founder (so the demo tree is clean and deep).
            if (row[3] == 'M' and row[6] == 'Muslim'
                    and row[11] and SPOUSE_SEP not in row[11]
                    and int(row[5][:4]) <= FOUNDER_MAX_YEAR):
                seen_candidates += 1
                if len(husbands) < NUM_HUSBANDS:
                    husbands.append(row)
                else:
                    j = random.randint(0, seen_candidates - 1)
                    if j < NUM_HUSBANDS:
                        husbands[j] = row

    if not husbands:
        print("No eligible married Muslim founder men found. Nothing to do.")
        return
    print(f"  Selected {len(husbands)} husbands out of {seen_candidates} candidates.")

    # --- Generate the new wives + half-sibling children ---
    new_nids = set()
    new_brns = set()

    def gen_nid(year, dist):
        code = dcodes.get(dist, '00')
        while True:
            nid = f"{year}{code}{random.randint(1000000, 9999999)}"
            if int(nid) not in existing_nids and nid not in new_nids:
                new_nids.add(nid)
                return nid

    def gen_brn(year):
        while True:
            brn = f"{year}{random.randint(1000000000000, 9999999999999)}"
            if brn not in new_brns:
                new_brns.add(brn)
                return brn

    new_rows = []                 # all appended wife + child rows
    husband_updates = {}          # husband_nid -> new pipe-separated spouse_nid
    report = []                   # summary lines for the console

    for h in husbands:
        h_nid, h_name = h[0], h[2]
        h_year = int(h[5][:4])
        cfg = gen_cfg(h_year)
        surname = h_name.split()[-1]
        h_perm, h_pres = h[12], h[13]
        h_dist = h_perm.split(',')[-2].strip()

        wife_nids = [h[11]]       # keep the existing wife first
        n_new_kids = 0
        n_extra = random.randint(*EXTRA_WIVES)

        for _ in range(n_extra):
            wloc, wdist = weighted_location()
            w_year = random.randint(*cfg['wife_year'])
            w_nid = gen_nid(w_year, wdist)
            w_brn = gen_brn(w_year)
            w_first = random.choice(names['Muslim']['gen_1_2']['female_first'])
            w_surname = random.choice(names['Muslim']['gen_1_2']['surnames'])
            w_name = f"{w_first} {w_surname}"

            # New wife: her own founder record, married to this husband.
            new_rows.append([
                w_nid, w_brn, w_name, 'F', random.choice(BLOOD),
                f"{w_year}-01-01", 'Muslim', 'Unknown', 'Unknown', '', '',
                h_nid, wloc, wloc, 'False'
            ])
            wife_nids.append(w_nid)

            # Her children -> half-siblings of the husband's existing children.
            start = max(h_year + 21, w_year + 18, cfg['child_range'][0])
            num_children = random.randint(*cfg['k_range'])
            birth_year = start
            for i in range(num_children):
                if i > 0:
                    birth_year += random.randint(1, 4)   # 1-4 year sibling gap
                if birth_year > cfg['child_range'][1]:
                    break
                cg = 'M' if random.random() < 0.5 else 'F'
                pool = names['Muslim'][cfg['name_gen']]
                c_first = random.choice(pool['male_first' if cg == 'M' else 'female_first'])
                c_name = f"{c_first} {surname}"          # inherit father's surname
                c_nid = gen_nid(birth_year, h_dist)
                c_brn = gen_brn(birth_year)
                new_rows.append([
                    c_nid, c_brn, c_name, cg, random.choice(BLOOD),
                    f"{birth_year}-06-15", 'Muslim', h_name, w_name,
                    h_nid, w_nid, '',                    # father=husband, mother=this wife
                    h_perm, h_pres, str(h_perm != h_pres)
                ])
                n_new_kids += 1

        husband_updates[h_nid] = SPOUSE_SEP.join(wife_nids)
        report.append((h_nid, h_name, len(wife_nids), wife_nids[1:], n_new_kids))

    print(f"  Generated {len(new_rows)} new rows "
          f"({sum(r[2] - 1 for r in report)} wives + "
          f"{sum(r[4] for r in report)} children).")

    # --- Pass 2: rewrite the CSV (update husbands in place, append new rows) ---
    print("Pass 2: rewriting CSV with the injected marriages...")
    tmp_file = CSV_FILE + '.tmp'
    changed_husband_rows = []

    with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as fin, \
         open(tmp_file, 'w', newline='', encoding='utf-8-sig') as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(next(reader))  # header
        for row in reader:
            if row[0] in husband_updates:
                row[11] = husband_updates[row[0]]
                changed_husband_rows.append(list(row))
            writer.writerow(row)
        writer.writerows(new_rows)

    os.replace(tmp_file, CSV_FILE)

    # --- Delta file: only the rows a graph needs to add these marriages ---
    delta_rows = changed_husband_rows + new_rows
    with open(DELTA_FILE, 'w', newline='', encoding='utf-8-sig') as fdelta:
        writer = csv.writer(fdelta, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(HEADER)
        writer.writerows(delta_rows)

    # --- Report ---
    print("\n" + "=" * 70)
    print("POLYGYNOUS HUSBANDS CREATED (search these NIDs in the app):")
    print("=" * 70)
    for h_nid, h_name, total_wives, new_wives, n_kids in report:
        print(f"  NID {h_nid}  {h_name}")
        print(f"      total wives: {total_wives}  |  new wives: {', '.join(new_wives)}")
        print(f"      new children (half-siblings): {n_kids}")
    print("=" * 70)
    print(f"Updated {CSV_FILE}  (+{len(new_rows)} rows)")
    print(f"Wrote   {DELTA_FILE}  ({len(delta_rows)} rows)")

    if push_to_neo4j:
        push_delta_to_neo4j(delta_rows)
    else:
        print("\nTo load these into Neo4j so the graph shows them, either:")
        print("  * python inject_multiple_marriages.py --neo4j   (fast, delta only)")
        print("  * python neo4j_import.py                        (full re-import)")

    print(f"\nDone in {time.time() - t0:.1f}s.")


def push_delta_to_neo4j(delta_rows):
    """Push only the changed/new rows into Neo4j, reusing the exact MERGE logic
    from neo4j_import.py (which already understands pipe-separated spouse_nid)."""
    print("\nPushing delta into Neo4j...")
    try:
        from neo4j import GraphDatabase
        import neo4j_import as ni
    except Exception as e:
        print(f"  Could not import Neo4j driver / neo4j_import.py: {e}")
        return

    batch = []
    for row in delta_rows:
        d = dict(zip(HEADER, row))
        d['father_nid'] = d['father_nid'] or None
        d['mother_nid'] = d['mother_nid'] or None
        d['spouse_nid'] = d['spouse_nid'] or None
        batch.append(d)

    try:
        driver = GraphDatabase.driver(ni.URI, auth=(ni.USERNAME, ni.PASSWORD))
        with driver.session(database=ni.DATABASE) as session:
            session.execute_write(ni.create_nodes_tx, batch)          # nodes first
            session.execute_write(ni.create_relationships_tx, batch)  # then edges
        driver.close()
        print(f"  Merged {len(batch)} nodes and their relationships into Neo4j.")
    except Exception as e:
        print(f"  Neo4j push failed ({e}).")
        print(f"  Is Neo4j running at {ni.URI}? You can also run: python neo4j_import.py")


if __name__ == '__main__':
    main()
