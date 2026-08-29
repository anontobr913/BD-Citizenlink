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
from datetime import datetime

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

        # find uncles & aunts (a parent's siblings, on both sides). They share a
        # GRANDPARENT with one of the root's parents, so we hang them off that
        # grandparent (already on the canvas from the ancestor query). This lets
        # the classifier label them Uncle / Aunt and the View Table sort them
        # onto the correct side. They are hidden from the graph itself (app.js).
        uncle_result = session.run("""
            MATCH (c:Citizen {nid: $nid})-[:HAS_FATHER|HAS_MOTHER]->(parent)
                  -[:HAS_FATHER|HAS_MOTHER]->(gp)<-[ur:HAS_FATHER|HAS_MOTHER]-(uncle)
            WHERE uncle.nid <> parent.nid AND uncle.nid <> $nid
            RETURN DISTINCT uncle, gp.nid AS gp_nid, type(ur) AS uncle_rel
        """, nid=nid)
        uncle_ids = set()
        for rec in uncle_result:
            unc = rec["uncle"]
            u_nid = unc["nid"]
            if u_nid not in nodes:
                n = _node_to_dict(unc)
                n["_role"] = "uncle"
                nodes[u_nid] = n
            uncle_ids.add(u_nid)
            if rec["gp_nid"] in nodes:
                edges.append({"source": u_nid, "target": rec["gp_nid"], "type": rec["uncle_rel"]})

        # cousins = the uncles'/aunts' children. Shown in the View Table only
        # (hidden from the graph like the uncles/aunts themselves).
        if uncle_ids:
            cousin2_result = session.run("""
                UNWIND $uncles AS u_nid
                MATCH (cousin)-[cr:HAS_FATHER|HAS_MOTHER]->(uncle:Citizen {nid: u_nid})
                WHERE cousin.nid <> $nid
                RETURN DISTINCT cousin, u_nid AS uncle_nid, type(cr) AS cousin_rel
            """, uncles=list(uncle_ids), nid=nid)
            for rec in cousin2_result:
                cous = rec["cousin"]
                c2_nid = cous["nid"]
                if c2_nid not in nodes:
                    n = _node_to_dict(cous)
                    n["_role"] = "cousin"
                    nodes[c2_nid] = n
                edges.append({"source": c2_nid, "target": rec["uncle_nid"], "type": rec["cousin_rel"]})

        # finally, pull in the marriages that the multiple-marriage view needs:
        #   * the root's own spouses -> a wife sees her co-wives through the
        #     husband they share
        #   * the root's DIRECT parents' spouses -> a child sees the father's
        #     other wives (their step-mothers)
        # Everyone else's marriages are deliberately skipped. Expanding children,
        # siblings, cousins -- or deeper ancestors like grandparents -- only drags
        # in-laws onto the canvas (sons-in-law, sisters-in-law, and grandparents'
        # other spouses that show up as "grandmother-in-law"). This tree is about
        # the household, not who married into it.
        root_parents = {e["target"] for e in edges
                        if e["source"] == nid and e["type"] in ("HAS_FATHER", "HAS_MOTHER")}
        existing_nids = [n for n, d in nodes.items()
                         if d.get("_role") == "spouse" or n in root_parents]
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

        # Fill in every parent link between two people who are already on the
        # canvas. The queries above each follow a single line at a time, so a
        # half-sibling would otherwise hang off the shared father only, and all
        # of a polygynous man's children would collapse into one undifferentiated
        # pile instead of one branch per wife.
        parents = _fetch_parents(session, list(nodes.keys()))
        for child_nid, pair in parents.items():
            for parent_key, rel_type in (("father", "HAS_FATHER"),
                                         ("mother", "HAS_MOTHER")):
                parent_nid = pair[parent_key]
                if parent_nid and parent_nid in nodes:
                    edges.append({
                        "source": child_nid,
                        "target": parent_nid,
                        "type": rel_type
                    })

        # The cousin query adds generic HAS_PARENT links; drop the ones the step
        # above just superseded with a real father/mother link.
        typed_pairs = {(e["source"], e["target"]) for e in edges
                       if e["type"] in ("HAS_FATHER", "HAS_MOTHER")}
        edges = [e for e in edges
                 if e["type"] != "HAS_PARENT"
                 or (e["source"], e["target"]) not in typed_pairs]

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
        _compute_all_relationships(nid, nodes, unique_edges, parents)

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

        # Both people's parents, so the classifier can tell a full sibling
        # from a half sibling.
        parents = _fetch_parents(session, [nid1, nid2])

        # Classify the relationship
        label = _classify_relationship(nid1, nid2, path_nodes, path_rels, parents)

        # For a co-wife the person in the middle of the path is the shared
        # husband, which is the one detail that makes the label make sense.
        middle_name = path_nodes[1].get("full_name") if len(path_nodes) == 3 else None
        detail = _relationship_detail(
            label, parents.get(nid1), parents.get(nid2), middle_name
        )

        return jsonify({
            "found": True,
            "relationship": label,
            "detail": detail,
            "path_nodes": path_nodes,
            "path_rels": path_rels,
            "path_length": len(path_rels)
        })


def _classify_relationship(nid1, nid2, path_nodes, path_rels, parents=None):
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

    # Multiple marriages get named first (see _marriage_label).
    parents = parents or {}
    married = _marriage_label(moves, nid2_gender == "M",
                              parents.get(nid1), parents.get(nid2))
    if married:
        return married

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


def _compute_all_relationships(root_nid, nodes, edges, parents=None):
    """
    Walk through the family tree graph starting from root_nid.
    For each person, determine their specific relationship to the root
    (e.g., Father, Grandmother, Uncle, Cousin) instead of generic labels.

    `parents` is {nid: {'father': nid, 'mother': nid}} and is what lets us tell
    a half sibling from a full one.
    """
    parents = parents or {}

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
    # came_from remembers who we arrived through, so a co-wife label can name
    # the husband the two women share.
    visited = {root_nid: []}
    came_from = {}
    queue = deque([root_nid])

    while queue:
        current = queue.popleft()
        current_path = visited[current]

        for neighbor_nid, direction, rel_type in adjacency[current]:
            if neighbor_nid not in visited:
                visited[neighbor_nid] = current_path + [(direction, rel_type)]
                came_from[neighbor_nid] = current
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
        root_parents, own_parents = parents.get(root_nid), parents.get(nid)
        label = _label_from_path(path, gender, root_parents, own_parents)
        node["_role"] = label

        via_nid = came_from.get(nid)
        middle_name = nodes.get(via_nid, {}).get("full_name") if via_nid else None
        detail = _relationship_detail(label, root_parents, own_parents, middle_name)
        if detail:
            node["_via"] = detail


def _label_from_path(moves, target_gender, root_parents=None, target_parents=None):
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

    # Multiple marriages get named first (see _marriage_label).
    married = _marriage_label(moves, is_male, root_parents, target_parents)
    if married:
        return married

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


# ---------------------------------------------------------------------------
# Multiple marriages
# ---------------------------------------------------------------------------
# Islam permits a man up to four wives, so the data contains households where
# one husband has several wives and each wife has her own children. That
# creates four relationships an ordinary family tree never has to name, and the
# move-counting above cannot name them on its own: it sees "one parent hop plus
# one marriage hop" and has no way to tell a father's second wife from a wife's
# mother, because it never looks at the order the hops came in.


def _fetch_parents(session, nids):
    """Return {nid: {'father': nid|None, 'mother': nid|None}} for these people."""
    result = session.run("""
        UNWIND $nids AS wanted
        MATCH (c:Citizen {nid: wanted})
        OPTIONAL MATCH (c)-[:HAS_FATHER]->(f)
        OPTIONAL MATCH (c)-[:HAS_MOTHER]->(m)
        RETURN c.nid AS nid, f.nid AS father, m.nid AS mother
    """, nids=nids)
    return {
        rec["nid"]: {"father": rec["father"], "mother": rec["mother"]}
        for rec in result
    }


def _shared_parents(a, b):
    """Which parents two people have in common: 'father', 'mother', or both."""
    a, b = a or {}, b or {}
    shared = []
    if a.get("father") and a["father"] == b.get("father"):
        shared.append("father")
    if a.get("mother") and a["mother"] == b.get("mother"):
        shared.append("mother")
    return shared


def _shares_one_parent(a, b):
    """
    True only when both people have both parents on record and exactly one of
    them matches. A missing parent is not a different parent, so when anything
    is unknown we say nothing and let them stay plain siblings.
    """
    if not a or not b:
        return False
    if not all(a.get(key) and b.get(key) for key in ("father", "mother")):
        return False
    return len(_shared_parents(a, b)) == 1


def _marriage_label(moves, is_male, root_parents=None, target_parents=None):
    """
    Name the four relationships that only appear once someone has married more
    than once. Returns None for everything else, leaving ordinary relatives to
    the tables above.
    """
    steps = [move[0] for move in moves]

    # Married to the same person I am married to.
    if steps == ["SPOUSE", "SPOUSE"]:
        return "Co-Husband" if is_male else "Co-Wife"

    # Up to a parent, then across to their other spouse. My own mother is a
    # single hop away, so she is never the one found here.
    if steps == ["UP", "SPOUSE"]:
        return "Step-Father" if is_male else "Step-Mother"

    # Across to my spouse, then down to a child who is not mine.
    if steps == ["SPOUSE", "DOWN"]:
        return "Step-Son" if is_male else "Step-Daughter"

    # A sibling path, but only one parent in common.
    if steps == ["UP", "DOWN"] and _shares_one_parent(root_parents, target_parents):
        return "Half-Brother" if is_male else "Half-Sister"

    return None


def _relationship_detail(label, root_parents, target_parents, middle_name=None):
    """
    The one-line note that makes a multiple-marriage label make sense:
    which parent a half sibling shares, and whose husband two co-wives share.
    """
    if label in ("Half-Brother", "Half-Sister"):
        shared = _shared_parents(root_parents, target_parents)
        return "same " + shared[0] if shared else None

    if label in ("Co-Wife", "Co-Husband"):
        word = "husband" if label == "Co-Wife" else "wife"
        return "shares " + word + " " + middle_name if middle_name else "shares a " + word

    return None


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


# get inheritors (children) of a citizen by NID
@app.route("/api/inheritors/<nid>")
def get_inheritors(nid):
    """Return all children of a citizen — i.e. anyone whose father or mother is this NID."""
    with driver.session(database=NEO4J_DB) as session:
        # verify the citizen exists
        root_rec = session.run(
            "MATCH (c:Citizen {nid: $nid}) RETURN c.full_name AS name", nid=nid
        ).single()
        if not root_rec:
            return jsonify({"error": "Citizen not found"}), 404

        parent_name = root_rec["name"]

        # find all children (anyone pointing HAS_FATHER or HAS_MOTHER to this NID)
        result = session.run("""
            MATCH (child)-[:HAS_FATHER|HAS_MOTHER]->(parent:Citizen {nid: $nid})
            RETURN properties(child) AS child
            ORDER BY child.dob
        """, nid=nid)
        children = [rec["child"] for rec in result]

    return jsonify({
        "parent_nid": nid,
        "parent_name": parent_name,
        "children": children
    })


# minimum days between consecutive births to be considered normal
MIN_BIRTH_GAP_DAYS = 270   # ~9 months


@app.route("/api/birth-audit/<father_nid>/<mother_nid>")
def birth_audit(father_nid, mother_nid):
    """
    Audit birth registrations for a couple.
    Returns all shared children sorted by DOB with flags:
      - same-day births → twins/triplets (allowed)
      - gap < MIN_BIRTH_GAP_DAYS → 🚩 flagged
      - gap >= MIN_BIRTH_GAP_DAYS → ✅ normal
    """
    with driver.session(database=NEO4J_DB) as session:
        # verify both parents exist
        for label, check_nid in [("Father", father_nid), ("Mother", mother_nid)]:
            rec = session.run(
                "MATCH (c:Citizen {nid: $nid}) RETURN c.full_name AS name, c.gender AS gender",
                nid=check_nid
            ).single()
            if not rec:
                return jsonify({"error": f"{label} NID {check_nid} not found"}), 404

        # fetch parent names
        father_rec = session.run(
            "MATCH (c:Citizen {nid: $nid}) RETURN c.full_name AS name", nid=father_nid
        ).single()
        mother_rec = session.run(
            "MATCH (c:Citizen {nid: $nid}) RETURN c.full_name AS name", nid=mother_nid
        ).single()

        # find all children shared by BOTH this father and this mother
        result = session.run("""
            MATCH (child)-[:HAS_FATHER]->(f:Citizen {nid: $father_nid}),
                  (child)-[:HAS_MOTHER]->(m:Citizen {nid: $mother_nid})
            RETURN properties(child) AS child
            ORDER BY child.dob
        """, father_nid=father_nid, mother_nid=mother_nid)
        children = [rec["child"] for rec in result]

    if not children:
        return jsonify({
            "father_nid": father_nid,
            "father_name": father_rec["name"],
            "mother_nid": mother_nid,
            "mother_name": mother_rec["name"],
            "children": [],
            "flags": [],
            "total_flags": 0,
            "twins_found": 0
        })

    # parse DOBs and check consecutive gaps
    def _parse_dob(dob_str):
        """Try several date formats the data might use."""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y"):
            try:
                return datetime.strptime(dob_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    flags = []
    twins_count = 0

    for i in range(1, len(children)):
        prev = children[i - 1]
        curr = children[i]
        prev_dob = _parse_dob(prev.get("dob", ""))
        curr_dob = _parse_dob(curr.get("dob", ""))

        if not prev_dob or not curr_dob:
            continue

        gap_days = (curr_dob - prev_dob).days

        if gap_days == 0:
            # same day → twins/triplets, allowed
            twins_count += 1
            flags.append({
                "child_a_nid": prev["nid"],
                "child_a_name": prev["full_name"],
                "child_b_nid": curr["nid"],
                "child_b_name": curr["full_name"],
                "gap_days": gap_days,
                "status": "twins",
                "message": "Same-day birth — twins/triplets (allowed)"
            })
        elif gap_days < MIN_BIRTH_GAP_DAYS:
            # suspiciously close
            flags.append({
                "child_a_nid": prev["nid"],
                "child_a_name": prev["full_name"],
                "child_b_nid": curr["nid"],
                "child_b_name": curr["full_name"],
                "gap_days": gap_days,
                "status": "flagged",
                "message": f"Only {gap_days} days apart (minimum {MIN_BIRTH_GAP_DAYS})"
            })
        else:
            flags.append({
                "child_a_nid": prev["nid"],
                "child_a_name": prev["full_name"],
                "child_b_nid": curr["nid"],
                "child_b_name": curr["full_name"],
                "gap_days": gap_days,
                "status": "ok",
                "message": f"{gap_days} days apart — normal"
            })

    total_flags = sum(1 for f in flags if f["status"] == "flagged")

    return jsonify({
        "father_nid": father_nid,
        "father_name": father_rec["name"],
        "mother_nid": mother_nid,
        "mother_name": mother_rec["name"],
        "children": children,
        "flags": flags,
        "total_flags": total_flags,
        "twins_found": twins_count,
        "min_gap_days": MIN_BIRTH_GAP_DAYS
    })


# serve the main frontend page
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # Open via 127.0.0.1, NOT localhost. On Windows `localhost` resolves to IPv6
    # ::1 first; this dev server is IPv4-only, so the browser waits ~2s for the
    # ::1 connection to fail before falling back to 127.0.0.1 -- a flat ~2s added
    # to EVERY request (including the family-tree fetch, which is why the tree
    # felt slow to build). Hitting 127.0.0.1 directly skips that failover.
    print("Starting Family Tree Visualization Server...")
    print("Open http://127.0.0.1:5000 in your browser  (use 127.0.0.1, not localhost)")
    app.run(debug=True, port=5000)
