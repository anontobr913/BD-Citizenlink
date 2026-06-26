import csv
import time
from neo4j import GraphDatabase

# neo4j database connection settings
URI = "neo4j://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "913913913"  # update this if your local neo4j password is different
DATABASE = "neo4j"      # update this if your database has a different name

def import_data():
    """
    Main function to read citizen data from CSV and import it into Neo4j.
    It does this in two passes: first creating all citizen nodes, 
    and then creating the relationships (parents, spouse) between them.
    """
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    csv_file = "Nid_data_create.csv"
    batch_size = 10000
    
    with driver.session(database=DATABASE) as session:
        print("Creating index on Citizen NID (this makes imports incredibly fast)...")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Citizen) REQUIRE c.nid IS UNIQUE")
        
        # Wait for the constraint to be online
        time.sleep(2)
        
        print("Pass 1: Creating Citizen nodes...")
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            batch = []
            count = 0
            
            for row in reader:
                # Remove empty string IDs so we don't accidentally link people with no parents
                row['father_nid'] = row['father_nid'] if row['father_nid'] else None
                row['mother_nid'] = row['mother_nid'] if row['mother_nid'] else None
                row['spouse_nid'] = row['spouse_nid'] if row['spouse_nid'] else None
                
                batch.append(row)
                if len(batch) >= batch_size:
                    session.execute_write(create_nodes_tx, batch)
                    count += len(batch)
                    print(f"Created {count} nodes...")
                    batch = []
            if batch:
                session.execute_write(create_nodes_tx, batch)
                count += len(batch)
                print(f"Created {count} nodes (Finished Pass 1)")
                
        print("\nPass 2: Creating Relationships (Father, Mother, Spouse)...")
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            batch = []
            count = 0
            
            for row in reader:
                # We only need the NIDs to create relationships
                batch.append({
                    "nid": row["nid"],
                    "father_nid": row["father_nid"] if row["father_nid"] else None,
                    "mother_nid": row["mother_nid"] if row["mother_nid"] else None,
                    "spouse_nid": row["spouse_nid"] if row["spouse_nid"] else None
                })
                if len(batch) >= batch_size:
                    session.execute_write(create_relationships_tx, batch)
                    count += len(batch)
                    print(f"Processed relationships for {count} rows...")
                    batch = []
            if batch:
                session.execute_write(create_relationships_tx, batch)
                count += len(batch)
                print(f"Processed relationships for {count} rows (Finished Pass 2)")

    driver.close()
    print("\nImport complete!")

def create_nodes_tx(tx, batch):
    """
    Transaction block to create citizen nodes in batches.
    We use MERGE to ensure we don't create duplicate citizens if the script is run twice.
    """
    query = """
    UNWIND $batch AS row
    MERGE (c:Citizen {nid: row.nid})
    SET c.brn = row.brn,
        c.full_name = row.full_name,
        c.gender = row.gender,
        c.blood_group = row.blood_group,
        c.dob = row.dob,
        c.religion = row.religion,
        c.perm_address = row.perm_address,
        c.pres_address = row.pres_address
    """
    tx.run(query, batch=batch)

def create_relationships_tx(tx, batch):
    """
    Transaction block to establish family relationships between citizens.
    We handle fathers, mothers, and spouses in separate queries within the same transaction.
    """
    father_query = """
    UNWIND $batch AS row
    WITH row WHERE row.father_nid IS NOT NULL
    MATCH (child:Citizen {nid: row.nid})
    MATCH (father:Citizen {nid: row.father_nid})
    MERGE (child)-[:HAS_FATHER]->(father)
    """
    tx.run(father_query, batch=batch)

    mother_query = """
    UNWIND $batch AS row
    WITH row WHERE row.mother_nid IS NOT NULL
    MATCH (child:Citizen {nid: row.nid})
    MATCH (mother:Citizen {nid: row.mother_nid})
    MERGE (child)-[:HAS_MOTHER]->(mother)
    """
    tx.run(mother_query, batch=batch)

    spouse_query = """
    UNWIND $batch AS row
    WITH row WHERE row.spouse_nid IS NOT NULL AND row.nid < row.spouse_nid
    MATCH (c1:Citizen {nid: row.nid})
    MATCH (c2:Citizen {nid: row.spouse_nid})
    MERGE (c1)-[:MARRIED_TO]-(c2)
    """
    tx.run(spouse_query, batch=batch)

if __name__ == "__main__":
    print("Starting Neo4j Import...")
    t0 = time.time()
    import_data()
    print(f"Total time taken: {time.time() - t0:.2f} seconds")
