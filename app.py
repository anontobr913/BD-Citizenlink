"""
Family Tree Visualization & Relationship Finder
Flask backend with Neo4j graph database integration.

Features:
  - Complete Family Hierarchy Visualization
  - Interactive Family Navigation
  - Relationship Finder
"""

from flask import Flask, jsonify, render_template, request
from neo4j import GraphDatabase
from collections import defaultdict, deque

app = Flask(__name__)

# database connection settings
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "913913913"   # change this if your local neo4j password is different
NEO4J_DB   = "neo4j"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def _node_to_dict(node):
    """Convert a Neo4j node to a plain dictionary."""
    d = dict(node)
    return d


# get citizen profile by NID
@app.route("/api/citizen/<nid>")
def get_citizen(nid):
    """Return the full profile for a single citizen."""
    with driver.session(database=NEO4J_DB) as session:
        result = session.run(
            "MATCH (c:Citizen {nid: $nid}) RETURN c", nid=nid
        )
        record = result.single()
        if not record:
            return jsonify({"error": "Citizen not found"}), 404
        return jsonify(_node_to_dict(record["c"]))


# get the full family tree including ancestors, descendants, siblings, and spouse
@app.route("/api/family-tree/<nid>")
def get_family_tree(nid):
    """
    Build the complete family hierarchy for a citizen:
      - Ancestors   (parents, grandparents, … up to 10 levels)
      - Descendants (children, grandchildren, … up to 10 levels)
      - Siblings    (same father or mother)
      - Spouse
      - Cousins     (children of parent's siblings)
    """
    with driver.session(database=NEO4J_DB) as session:

        # fetch the root citizen first
        root_rec = session.run(
            "MATCH (c:Citizen {nid: $nid}) RETURN c", nid=nid
        ).single()
        if not root_rec:
            return jsonify({"error": "Citizen not found"}), 404

        root = _node_to_dict(root_rec["c"])
        root["_role"] = "self"

        nodes = {nid: root}           # nid -> node dict
        edges = []                    # list of {source, target, type}

        # helper function to safely add nodes and relationships to our lists
        def _add(node, role, edge_source, edge_target, edge_type):
            n = _node_to_dict(node)
            n["_role"] = role
            nid_val = n["nid"]
            if nid_val not in nodes:
                nodes[nid_val] = n
            edges.append({
                "source": edge_source,
                "target": edge_target,
                "type": edge_type
            })

        # find ancestors up to 10 generations back
        anc_result = session.run("""
            MATCH path = (c:Citizen {nid: $nid})-[:HAS_FATHER|HAS_MOTHER*1..10]->(ancestor)
            UNWIND relationships(path) AS rel
            WITH startNode(rel) AS child, endNode(rel) AS parent, type(rel) AS rtype
            RETURN DISTINCT child.nid AS child_nid,
                            parent.nid AS parent_nid,
                            properties(parent) AS parent_props,
                            properties(child) AS child_props,
                            rtype
        """, nid=nid)
        for rec in anc_result:
            p_nid = rec["parent_nid"]
            if p_nid not in nodes:
                p = rec["parent_props"]
                p["_role"] = "ancestor"
                nodes[p_nid] = p
            c_nid = rec["child_nid"]
            if c_nid not in nodes:
                c = rec["child_props"]
                c["_role"] = "ancestor"
                nodes[c_nid] = c
            edges.append({
                "source": rec["child_nid"],
                "target": rec["parent_nid"],
                "type": rec["rtype"]
            })

        # find descendants up to 10 generations forward
        desc_result = session.run("""
            MATCH path = (desc)-[:HAS_FATHER|HAS_MOTHER*1..10]->(c:Citizen {nid: $nid})
            UNWIND relationships(path) AS rel
            WITH startNode(rel) AS child, endNode(rel) AS parent, type(rel) AS rtype
            RETURN DISTINCT child.nid AS child_nid,
                            parent.nid AS parent_nid,
                            properties(child) AS child_props,
                            properties(parent) AS parent_props,
                            rtype
        """, nid=nid)
        for rec in desc_result:
            c_nid = rec["child_nid"]
            if c_nid not in nodes:
                c = rec["child_props"]
                c["_role"] = "descendant"
                nodes[c_nid] = c
            p_nid = rec["parent_nid"]
            if p_nid not in nodes:
                p = rec["parent_props"]
                p["_role"] = "descendant"
                nodes[p_nid] = p
            edges.append({
                "source": rec["child_nid"],
                "target": rec["parent_nid"],
                "type": rec["rtype"]
            })

        # find the spouse
        spouse_result = session.run("""
            MATCH (c:Citizen {nid: $nid})-[:MARRIED_TO]-(spouse)
            RETURN spouse
        """, nid=nid)
        for rec in spouse_result:
            sp = rec["spouse"]
            _add(sp, "spouse", nid, sp["nid"], "MARRIED_TO")

        # find siblings by checking for shared parents
        sibling_result = session.run("""
            MATCH (c:Citizen {nid: $nid})-[:HAS_FATHER]->(f)<-[:HAS_FATHER]-(sib)
            WHERE sib.nid <> $nid
            RETURN DISTINCT sib, f.nid AS via_parent, 'HAS_FATHER' AS via_rel
            UNION
            MATCH (c:Citizen {nid: $nid})-[:HAS_MOTHER]->(m)<-[:HAS_MOTHER]-(sib)
            WHERE sib.nid <> $nid
            RETURN DISTINCT sib, m.nid AS via_parent, 'HAS_MOTHER' AS via_rel
        """, nid=nid)
        seen_siblings = set()
        for rec in sibling_result:
            sib = rec["sib"]
            s_nid = sib["nid"]
            if s_nid not in seen_siblings:
                seen_siblings.add(s_nid)
                _add(sib, "sibling", s_nid, rec["via_parent"], rec["via_rel"])

        # find cousins by getting children of uncles and aunts
        cousin_result = session.run("""
            MATCH (c:Citizen {nid: $nid})-[:HAS_FATHER]->(f)<-[:HAS_FATHER]-(uncle)
            WHERE uncle.nid <> $nid
            MATCH (cousin)-[:HAS_FATHER|HAS_MOTHER]->(uncle)
            RETURN DISTINCT cousin, uncle.nid AS uncle_nid
            UNION
            MATCH (c:Citizen {nid: $nid})-[:HAS_MOTHER]->(m)<-[:HAS_MOTHER]-(aunt)
            WHERE aunt.nid <> $nid
            MATCH (cousin)-[:HAS_FATHER|HAS_MOTHER]->(aunt)
            RETURN DISTINCT cousin, aunt.nid AS uncle_nid
        """, nid=nid)
        for rec in cousin_result:
            cous = rec["cousin"]
            c_nid_val = cous["nid"]
            if c_nid_val not in nodes:
                n = _node_to_dict(cous)
                n["_role"] = "cousin"
                nodes[c_nid_val] = n
            edges.append({
                "source": c_nid_val,
                "target": rec["uncle_nid"],
                "type": "HAS_PARENT"
            })

        # finally, get spouses for all family members we just found
        existing_nids = list(nodes.keys())
        spouse_ext = session.run("""
            UNWIND $nids AS fam_nid
            MATCH (c:Citizen {nid: fam_nid})-[:MARRIED_TO]-(sp)
            RETURN c.nid AS from_nid, sp AS spouse
        """, nids=existing_nids)
        for rec in spouse_ext:
            sp = rec["spouse"]
            sp_nid = sp["nid"]
            if sp_nid not in nodes:
                n = _node_to_dict(sp)
                n["_role"] = "spouse"
                nodes[sp_nid] = n
            edges.append({
                "source": rec["from_nid"],
                "target": sp_nid,
                "type": "MARRIED_TO"
            })

        # De-duplicate edges
        unique_edges = []
        seen_edges = set()
        for e in edges:
            key = (e["source"], e["target"], e["type"])
            rev_key = (e["target"], e["source"], e["type"])
            if key not in seen_edges and rev_key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        # Compute specific relationship labels for every node
        _compute_all_relationships(nid, nodes, unique_edges)

    return jsonify({
        "root_nid": nid,
        "nodes": nodes,
        "edges": unique_edges
    })


# find the relationship path between two citizens
@app.route("/api/relationship/<nid1>/<nid2>")
def find_relationship(nid1, nid2):
    """
    Find the shortest path between two citizens and classify
    the relationship in human-readable form.
    """
    with driver.session(database=NEO4J_DB) as session:

        # Verify both citizens exist
        for check_nid in [nid1, nid2]:
            rec = session.run(
                "MATCH (c:Citizen {nid: $nid}) RETURN c.full_name AS name",
                nid=check_nid
            ).single()
            if not rec:
                return jsonify({"error": f"NID {check_nid} not found"}), 404

        # Find shortest path (limit length to 20 hops)
        result = session.run("""
            MATCH (a:Citizen {nid: $nid1}), (b:Citizen {nid: $nid2})
            MATCH path = shortestPath((a)-[:HAS_FATHER|HAS_MOTHER|MARRIED_TO*..20]-(b))
            RETURN [n IN nodes(path) | properties(n)] AS path_nodes,
                   [r IN relationships(path) |
                     {type: type(r),
                      start: startNode(r).nid,
                      end: endNode(r).nid}
                   ] AS path_rels
        """, nid1=nid1, nid2=nid2)

        record = result.single()
        if not record:
            return jsonify({
                "found": False,
                "message": "No relationship found between these two people."
            })

        path_nodes = record["path_nodes"]
        path_rels = record["path_rels"]

        # Classify the relationship
        label = _classify_relationship(nid1, nid2, path_nodes, path_rels)

        return jsonify({
            "found": True,
            "relationship": label,
            "path_nodes": path_nodes,
            "path_rels": path_rels,
            "path_length": len(path_rels)
        })


def _classify_relationship(nid1, nid2, path_nodes, path_rels):
    """
    Walk through the shortest path and produce a human-readable
    relationship label from nid1's perspective.

    Direction convention:
      - An edge (child)-[:HAS_FATHER]->(father) means
        if we go start→end we go child→father (UP)
        if we go end→start we go father→child (DOWN)
    """
    if len(path_rels) == 0:
        return "Same person"

    # Build a directed sequence of moves from nid1 toward nid2
    # Each move is ("UP", rel_type) or ("DOWN", rel_type) or ("SPOUSE",)
    moves = []
    current = nid1
    for rel in path_rels:
        rtype = rel["type"]
        start = rel["start"]
        end = rel["end"]

        if rtype == "MARRIED_TO":
            moves.append(("SPOUSE",))
            current = end if current == start else start
        elif rtype in ("HAS_FATHER", "HAS_MOTHER"):
            if current == start:
                # current is the child, going to parent → UP
                moves.append(("UP", rtype))
                current = end
            else:
                # current is the parent, going to child → DOWN
                moves.append(("DOWN", rtype))
                current = start
        else:
            moves.append(("UNKNOWN", rtype))
            current = end if current == start else start

    # extract the gender of the second person so we can use gendered labels (e.g. uncle vs aunt)
    nid2_gender = None
    for n in path_nodes:
        if n["nid"] == nid2:
            nid2_gender = n.get("gender", "")
            break

    # pattern matching to figure out the relationship based on the path moves
    ups = sum(1 for m in moves if m[0] == "UP")
    downs = sum(1 for m in moves if m[0] == "DOWN")
    spouses = sum(1 for m in moves if m[0] == "SPOUSE")

    # Direct parent
    if len(moves) == 1 and moves[0][0] == "UP":
        if moves[0][1] == "HAS_FATHER":
            return "Father"
        else:
            return "Mother"

    # Direct child
    if len(moves) == 1 and moves[0][0] == "DOWN":
        return "Son" if nid2_gender == "M" else "Daughter"

    # Spouse
    if len(moves) == 1 and moves[0][0] == "SPOUSE":
        return "Spouse (Husband)" if nid2_gender == "M" else "Spouse (Wife)"

    # Grandparent (2 ups)
    if ups == 2 and downs == 0 and spouses == 0:
        return "Grandfather" if nid2_gender == "M" else "Grandmother"

    # Grandchild (2 downs)
    if downs == 2 and ups == 0 and spouses == 0:
        return "Grandson" if nid2_gender == "M" else "Granddaughter"

    # Great-grandparent (3 ups)
    if ups == 3 and downs == 0 and spouses == 0:
        return "Great-Grandfather" if nid2_gender == "M" else "Great-Grandmother"

    # Great-grandchild (3 downs)
    if downs == 3 and ups == 0 and spouses == 0:
        return "Great-Grandson" if nid2_gender == "M" else "Great-Granddaughter"

    # Sibling (1 up + 1 down, no spouse)
    if ups == 1 and downs == 1 and spouses == 0:
        return "Brother" if nid2_gender == "M" else "Sister"

    # Uncle/Aunt (2 ups + 1 down, no spouse)
    if ups == 2 and downs == 1 and spouses == 0:
        return "Uncle" if nid2_gender == "M" else "Aunt"

    # Nephew/Niece (1 up + 2 downs, no spouse)
    if ups == 1 and downs == 2 and spouses == 0:
        return "Nephew" if nid2_gender == "M" else "Niece"

    # Cousin (2 ups + 2 downs, no spouse)
    if ups == 2 and downs == 2 and spouses == 0:
        return "Cousin"

    # Second cousin (3 ups + 3 downs, no spouse)
    if ups == 3 and downs == 3 and spouses == 0:
        return "Second Cousin"

    # Spouse's parent (spouse + 1 up) → Father-in-law / Mother-in-law
    if spouses == 1 and ups == 1 and downs == 0:
        return "Father-in-law" if nid2_gender == "M" else "Mother-in-law"

    # Spouse's sibling's area (spouse + ups + downs)
    if spouses == 1 and ups == 1 and downs == 1:
        return "Brother-in-law" if nid2_gender == "M" else "Sister-in-law"

    # Child's spouse (1 down + spouse)
    if spouses == 1 and downs == 1 and ups == 0:
        return "Son-in-law" if nid2_gender == "M" else "Daughter-in-law"

    # Great-uncle/aunt (3 ups + 1 down)
    if ups == 3 and downs == 1 and spouses == 0:
        return "Great-Uncle" if nid2_gender == "M" else "Great-Aunt"

    # General: more ups than downs → some ancestor relation
    if ups > 0 and downs == 0 and spouses == 0:
        gen = ups
        prefix = "Great-" * (gen - 2) if gen > 2 else ""
        base = "Grandfather" if nid2_gender == "M" else "Grandmother"
        return f"{prefix}{base}" if gen > 1 else ("Father" if nid2_gender == "M" else "Mother")

    # General: more downs than ups
    if downs > 0 and ups == 0 and spouses == 0:
        gen = downs
        prefix = "Great-" * (gen - 2) if gen > 2 else ""
        base = "Grandson" if nid2_gender == "M" else "Granddaughter"
        return f"{prefix}{base}" if gen > 1 else ("Son" if nid2_gender == "M" else "Daughter")

    # Fallback: describe the path
    return f"Related ({ups} gen up, {downs} gen down, {spouses} marriage link{'s' if spouses > 1 else ''})"


def _compute_all_relationships(root_nid, nodes, edges):
    """
    Walk through the family tree graph starting from root_nid.
    For each person, determine their specific relationship to the root
    (e.g., Father, Grandmother, Uncle, Cousin) instead of generic labels.
    """

    # Step 1: Build an adjacency list from the edges

    adjacency = defaultdict(list)

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        etype = edge["type"]

        if etype == "HAS_FATHER":
            # src is the child, tgt is the father
            adjacency[src].append((tgt, "UP", "HAS_FATHER"))
            adjacency[tgt].append((src, "DOWN", "HAS_FATHER"))
        elif etype == "HAS_MOTHER":
            adjacency[src].append((tgt, "UP", "HAS_MOTHER"))
            adjacency[tgt].append((src, "DOWN", "HAS_MOTHER"))
        elif etype == "MARRIED_TO":
            adjacency[src].append((tgt, "SPOUSE", "MARRIED_TO"))
            adjacency[tgt].append((src, "SPOUSE", "MARRIED_TO"))
        elif etype == "HAS_PARENT":
            # Generic parent link (used for cousins)
            adjacency[src].append((tgt, "UP", "HAS_PARENT"))
            adjacency[tgt].append((src, "DOWN", "HAS_PARENT"))

    # Step 2: BFS from the root to find the shortest path to every node
    # visited stores: nid -> list of (direction, rel_type) moves
    visited = {root_nid: []}
    queue = deque([root_nid])

    while queue:
        current = queue.popleft()
        current_path = visited[current]

        for neighbor_nid, direction, rel_type in adjacency[current]:
            if neighbor_nid not in visited:
                visited[neighbor_nid] = current_path + [(direction, rel_type)]
                queue.append(neighbor_nid)

    # Step 3: Classify the relationship for each node
    for nid, node in nodes.items():
        if nid == root_nid:
            node["_role"] = "Self"
            continue

        if nid not in visited:
            node["_role"] = "Related"
            continue

        path = visited[nid]
        gender = node.get("gender", "")
        node["_role"] = _label_from_path(path, gender)


def _label_from_path(moves, target_gender):
    """
    Given a path of moves from root to target, return a specific
    relationship name like 'Father', 'Grandmother', 'Uncle', etc.

    Each move is a tuple: (direction, rel_type)
      direction: 'UP' (toward parent), 'DOWN' (toward child), 'SPOUSE'
      rel_type:  'HAS_FATHER', 'HAS_MOTHER', 'MARRIED_TO', 'HAS_PARENT'
    """
    is_male = (target_gender == "M")

    # Count the number of each type of move
    ups = sum(1 for d, _ in moves if d == "UP")
    downs = sum(1 for d, _ in moves if d == "DOWN")
    spouses = sum(1 for d, _ in moves if d == "SPOUSE")
    total = len(moves)

    # direct relationships (only 1 step away)

    if total == 1:
        if moves[0][0] == "UP":
            if moves[0][1] == "HAS_FATHER":
                return "Father"
            return "Mother"
        if moves[0][0] == "DOWN":
            return "Son" if is_male else "Daughter"
        if moves[0][0] == "SPOUSE":
            return "Husband" if is_male else "Wife"

    # pure ancestor path (only going up)

    if ups > 0 and downs == 0 and spouses == 0:
        if ups == 2:
            return "Grandfather" if is_male else "Grandmother"
        if ups == 3:
            return "Great-Grandfather" if is_male else "Great-Grandmother"
        if ups >= 4:
            prefix = "Great-" * (ups - 2)
            return prefix + ("Grandfather" if is_male else "Grandmother")

    # pure descendant path (only going down)

    if downs > 0 and ups == 0 and spouses == 0:
        if downs == 2:
            return "Grandson" if is_male else "Granddaughter"
        if downs == 3:
            return "Great-Grandson" if is_male else "Great-Granddaughter"
        if downs >= 4:
            prefix = "Great-" * (downs - 2)
            return prefix + ("Grandson" if is_male else "Granddaughter")

    # siblings (up to a parent, then down to a child)

    if ups == 1 and downs == 1 and spouses == 0:
        return "Brother" if is_male else "Sister"

    # uncle or aunt (up to grandparents, then down to their child)

    if ups == 2 and downs == 1 and spouses == 0:
        return "Uncle" if is_male else "Aunt"

    # nephew or niece

    if ups == 1 and downs == 2 and spouses == 0:
        return "Nephew" if is_male else "Niece"

    # cousin

    if ups == 2 and downs == 2 and spouses == 0:
        return "Cousin"

    # great-uncle or great-aunt

    if ups == 3 and downs == 1 and spouses == 0:
        return "Great-Uncle" if is_male else "Great-Aunt"

    # second cousin

    if ups == 3 and downs == 3 and spouses == 0:
        return "Second Cousin"

    # in-law relationships involving a spouse link

    if spouses == 1 and ups == 1 and downs == 0:
        return "Father-in-law" if is_male else "Mother-in-law"

    if spouses == 1 and ups == 0 and downs == 1:
        return "Son-in-law" if is_male else "Daughter-in-law"

    if spouses == 1 and ups == 1 and downs == 1:
        return "Brother-in-law" if is_male else "Sister-in-law"

    if spouses == 1 and ups == 2 and downs == 0:
        return "Grandfather-in-law" if is_male else "Grandmother-in-law"

    if spouses == 1 and ups == 0 and downs == 0:
        return "Husband" if is_male else "Wife"

    # generic fallback if we don't have a specific label

    parts = []
    if ups > 0:
        parts.append(str(ups) + " gen up")
    if downs > 0:
        parts.append(str(downs) + " gen down")
    if spouses > 0:
        parts.append(str(spouses) + " marriage")
    return "Related (" + ", ".join(parts) + ")"


# search citizens by NID or partial name match
@app.route("/api/search")
def search_citizens():
    """Search citizens by NID (prefix match) or name (contains)."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])

    with driver.session(database=NEO4J_DB) as session:
        # Optimization: If the query is purely numeric, it's an NID search.
        # By separating this from the OR clause, Neo4j can instantly use the B-Tree index.
        if q.isdigit():
            result = session.run("""
                MATCH (c:Citizen)
                WHERE c.nid STARTS WITH $q
                RETURN properties(c) AS citizen
                LIMIT 20
            """, q=q)
        else:
            # If it contains letters, perform a name search.
            result = session.run("""
                MATCH (c:Citizen)
                WHERE toLower(c.full_name) CONTAINS toLower($q)
                RETURN properties(c) AS citizen
                LIMIT 20
            """, q=q.lower())
            
        citizens = [rec["citizen"] for rec in result]
    return jsonify(citizens)


# serve the main frontend page
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    print("Starting Family Tree Visualization Server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
