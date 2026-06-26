import json
import random
import csv
import time
from collections import defaultdict, deque

def fast_gen():
    t0 = time.time()
    
    print("Loading datasets...")
    with open('districts.json', 'r') as f: geo_data = json.load(f)
    with open('names.json', 'r') as f: name_data = json.load(f)

    # Rule 22: Geographic Distribution Rules
    divs = ['Dhaka', 'Chattogram', 'Rajshahi', 'Barishal', 'Khulna', 'Sylhet']
    weights = [30, 20, 15, 15, 10, 10]

    def get_weighted_location():
        chosen_div = random.choices(divs, weights=weights)[0]
        dist = random.choice(list(geo_data['divisions'][chosen_div].keys()))
        thana = random.choice(geo_data['divisions'][chosen_div][dist])
        return f"Holding {random.randint(1,500)}, {thana}, {dist}, {chosen_div}", dist

    generated_nids = set()
    generated_brns = set()

    # Rule 32, 33: BRN structure (4-digit year + 13 random digits)
    def generate_brn(year):
        while True:
            brn = f"{year}{random.randint(1000000000000, 9999999999999)}"
            if brn not in generated_brns:
                generated_brns.add(brn)
                return brn
        
    # Rule 31: NID structure (4-digit year + 2-digit dist + 7 random digits)
    def generate_nid(year, dist_name):
        d_code = geo_data['district_codes'].get(dist_name, '00')
        while True:
            nid = f"{year}{d_code}{random.randint(1000000, 9999999)}"
            if nid not in generated_nids:
                generated_nids.add(nid)
                return nid

    all_records = []
    gen_parents = []

    # Rule 19: Religion distribution
    religions = ['Muslim', 'Hindu', 'Buddhist', 'Christian']
    rel_weights = [90, 8, 1, 1]

    # Founder Generation (Gen-1)
    founder_count = 782500
    print(f"Generating Gen-1 Founders ({founder_count})...")
    
    for _ in range(founder_count):
        # Rule 27: Founder gender ratio (51% M, 49% F)
        gender = 'M' if random.random() < 0.51 else 'F'
        rel = random.choices(religions, weights=rel_weights)[0]
        
        # Rule 14: Founder birth years 1920-1940
        year = random.randint(1920, 1940)
        
        loc, dist = get_weighted_location()
        nid = generate_nid(year, dist)
        brn = generate_brn(year)
        
        # Rule 21: Name pool
        name_pool = name_data[rel]['gen_1_2']
        first = random.choice(name_pool['male_first' if gender=='M' else 'female_first'])
        surname = random.choice(name_pool['surnames'])
        full_name = f"{first} {surname}"
        
        row = [nid, brn, full_name, gender, random.choice(['A+','O+','B+','AB+','A-','O-','B-','AB-']), 
               f"{year}-01-01", rel, "Unknown", "Unknown", "", "", "", loc, loc, False]
        all_records.append(row)
        gen_parents.append(row)

    # Rule 18: Family tree depth limited to 4 generations (Gen 2, 3, 4)
    # Gen 2 -> rule 7: 90% marriage, rule 10: 4-8 children, rule 15: 1945-1965
    # Gen 3 -> rule 8: 80% marriage, rule 11: 2-6 children, rule 16: 1970-1985
    # Gen 4 -> rule 9: 60% marriage, rule 12: 1-4 children, rule 17: 1990-2015
    # Rule 13: Population growth decreases (inherent via k_range reducing)
    gens = [
        {"label": 2, "m_rate": 0.90, "k_range": (4, 8), "b_range": (1945, 1965)},
        {"label": 3, "m_rate": 0.80, "k_range": (2, 6), "b_range": (1970, 1985)},
        {"label": 4, "m_rate": 0.60, "k_range": (1, 4), "b_range": (1990, 2015)}
    ]

    for gen in gens:
        print(f"Processing Gen-{gen['label']}...")
        
        females_by_rel = defaultdict(deque)
        males = []
        
        for p in gen_parents:
            if p[3] == 'M':
                males.append(p)
            else:
                females_by_rel[p[6]].append(p)
                
        random.shuffle(males)
        next_gen_parents = []
        
        for father in males:
            # Rule 7, 8, 9: Marriage rates
            if random.random() > gen['m_rate']: continue
            
            rel = father[6]
            # Rule 5, 20: Couples must share same religion
            if not females_by_rel[rel]:
                continue
            
            mother = females_by_rel[rel].popleft()
            
            # Rule 6: Marriage linkage is mutual
            father[11] = mother[0] # spouse_nid
            mother[11] = father[0]
            
            # Rule 1 & 2: Father >= 21, Mother >= 18
            f_year = int(father[5][:4])
            m_year = int(mother[5][:4])
            min_biological_year = max(f_year + 21, m_year + 18)
            
            start_birth_year = max(min_biological_year, gen['b_range'][0])
            
            # Rule 10, 11, 12: Number of children
            num_children = random.randint(gen['k_range'][0], gen['k_range'][1])
            
            for i in range(num_children):
                # Rule 3: Sibling gap 1-4 years
                birth_year = start_birth_year + (i * random.randint(1, 4))
                
                # Rule 15, 16, 17: Enforce generation boundary
                if birth_year > gen['b_range'][1]: break
                
                # Rule 28: Child gender ratio (50/50)
                child_gender = 'M' if random.random() < 0.50 else 'F'
                
                # Rule 23: Child inherits father's surname
                surname = father[2].split()[-1]
                
                # Rule 26: Religion-based naming patterns preserved
                name_pool = name_data[rel]['gen_3_plus' if gen['label'] >= 3 else 'gen_1_2']
                first = random.choice(name_pool['male_first' if child_gender=='M' else 'female_first'])
                full_name = f"{first} {surname}"
                
                # NID Generation
                dist_name = father[12].split(',')[-2].strip()
                c_nid = generate_nid(birth_year, dist_name)
                c_brn = generate_brn(birth_year)
                
                # Rule 24, 25: Child inherits father's perm and pres address
                perm_address = father[12]
                pres_address = father[13]
                
                # Rule 4, 34: Parent relationships
                c_row = [c_nid, c_brn, full_name, child_gender, 
                         random.choice(['A+','O+','B+','AB+','A-','O-','B-','AB-']), f"{birth_year}-06-15", rel,
                         father[2], mother[2], father[0], mother[0], "", 
                         perm_address, pres_address, perm_address != pres_address]
                         
                all_records.append(c_row)
                next_gen_parents.append(c_row)
                
        gen_parents = next_gen_parents

    print(f"Total generated: {len(all_records)} records. Writing to CSV...")
    csv_filename = 'Nid_data_create.csv'
    
    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f_csv:
        writer = csv.writer(f_csv, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["nid","brn","full_name","gender","blood_group","dob","religion",
                         "father_name","mother_name","father_nid","mother_nid","spouse_nid",
                         "perm_address","pres_address","is_migrated"])
        writer.writerows(all_records)
        
    print(f"CSV Generated in {time.time() - t0:.2f} seconds.")

if __name__ == '__main__':
    fast_gen()
