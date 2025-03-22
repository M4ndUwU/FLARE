import os
import sqlite3
import pandas as pd

def get_matching_tables(db_path, patterns):
    """ Retrieves a list of tables that contain the given patterns """
    matching_tables = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]

        for table in tables:
            if any(pattern in table for pattern in patterns):
                matching_tables.append(table)

        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
    return matching_tables

def get_table_record_count(db_path, tables):
    """ Returns the number of records for specified tables """
    record_counts = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            record_counts[table] = cursor.fetchone()[0]

        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
    return record_counts

def compare_record_counts(base_counts, target_counts):
    """ Compares record counts between two databases and returns differences """
    differences = []
    for table in base_counts.keys():
        if base_counts[table] != target_counts.get(table, 0):
            differences.append((table, base_counts[table], target_counts.get(table, 0)))
    return differences

def process_db_comparisons(directory, table_patterns):
    """ Compares files like intact_a with header_section_corruption_a, etc. """
    db_files = [f for f in os.listdir(directory) if f.endswith(".db")]

    labels = ['a', 'b', 'c']
    results = []

    for label in labels:
        intact_files = [f for f in db_files if f"intact_{label}" in f]
        corrupt_files = [f for f in db_files if f"header_section_corruption_{label}" in f]

        for intact_file in intact_files:
            intact_path = os.path.join(directory, intact_file)
            matching_tables = get_matching_tables(intact_path, table_patterns)
            intact_counts = get_table_record_count(intact_path, matching_tables)

            for corrupt_file in corrupt_files:
                corrupt_path = os.path.join(directory, corrupt_file)

                if os.path.exists(intact_path) and os.path.exists(corrupt_path):
                    corrupt_counts = get_table_record_count(corrupt_path, matching_tables)

                    differences = compare_record_counts(intact_counts, corrupt_counts)
                    if differences:
                        results.append((intact_file, corrupt_file, differences))

    return results

directory_path = "./result/PX4/"
table_patterns = ['home_position', 'vehicle_global_position', 'vehicle_gps_position']
comparison_results = process_db_comparisons(directory_path, table_patterns)

# Print results
df_results = []
for base, target, diffs in comparison_results:
    for table, base_count, target_count in diffs:
        df_results.append([base, target, table, base_count, target_count])

df = pd.DataFrame(df_results, columns=["Base File", "Target File", "Table", "Base Count", "Target Count"])
print(df.to_string(index=False))
