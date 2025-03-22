import os
import sqlite3

def get_fmt_types(db_path, target_names):
    """Extracts the Type values from the FMT table for given target names."""
    types = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = f"""
            SELECT Name, Type FROM FMT
            WHERE Name IN ({','.join(['?'] * len(target_names))})
        """
        cursor.execute(query, target_names)
        types = {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
    finally:
        conn.close()
    return types

def count_byte_sequence(directory, sequences):
    """Counts occurrences of given byte sequences in all files within a directory."""
    results = {}

    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return results

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'rb') as file:
                data = file.read()
                total_count = sum(data.count(seq) for seq in sequences)
                results[filename] = total_count

    return results

# Define directories
db_dir = "./result/Ardupilot/"
test_dir = "./test/Ardupilot/"
target_prefixes = ["intact_a_", "intact_b_", "intact_c_"]
target_names = ['FMT', 'ADSB', 'AHR2', 'AIS1', 'AIS4', 'ARSP', 'BAT', 'BCL', 'CAM', 'CMD', 'DSTL', 'EAHR',
                'EV', 'FNCE', 'GPS', 'IMU', 'MOTB', 'OABR', 'OADJ', 'OAVG', 'ORGN', 'POS', 'RALY', 'TRIG', 'TRST']

db_files = [f for f in os.listdir(db_dir) if any(f.startswith(prefix) for prefix in target_prefixes) and f.endswith(".db")]
fmt_data = {}

# Collect FMT Type data from each database
for db_file in db_files:
    db_path = os.path.join(db_dir, db_file)
    fmt_data[db_file] = get_fmt_types(db_path, target_names)

# Generate byte sequences to search in test directory
test_sequences = []
for db, fmt_types in fmt_data.items():
    for name, type_val in fmt_types.items():
        test_sequences.append(bytes([0xA3, 0x95, int(type_val) & 0xFF]))

# Count occurrences in test directory
test_results = count_byte_sequence(test_dir, test_sequences)

# Compare differences
common_keys = set.intersection(*(set(fmt.keys()) for fmt in fmt_data.values()))
diff_results = {}

for key in common_keys:
    values = {db: fmt_data[db].get(key, None) for db in fmt_data}
    unique_values = set(values.values())
    if len(unique_values) > 1:
        diff_results[key] = values

# Print results
if diff_results:
    print("Differences found in FMT Type values:")
    for name, values in diff_results.items():
        print(f"{name}:")
        for db, type_val in values.items():
            print(f"  {db}: {type_val}")
else:
    print("No differences found in FMT Type values across databases.")

print("\nTotal Byte Sequence Count in ./test/Ardupilot/:")
for file, total_count in test_results.items():
    print(f"{file}: {total_count / 3}")


# Generate byte sequences separately for FMT and non-FMT
test_sequences_fmt = []
test_sequences_nonfmt = []

for db, fmt_types in fmt_data.items():
    for name, type_val in fmt_types.items():
        seq = bytes([0xA3, 0x95, int(type_val) & 0xFF])
        if name == 'FMT':
            test_sequences_fmt.append(seq)
        else:
            test_sequences_nonfmt.append(seq)

# Count occurrences separately
test_results_fmt = count_byte_sequence(test_dir, test_sequences_fmt)
test_results_nonfmt = count_byte_sequence(test_dir, test_sequences_nonfmt)

# Print results
print("\nTotal Byte Sequence Count in ./test/Ardupilot/:")

for file in sorted(set(test_results_fmt) | set(test_results_nonfmt)):
    fmt_count = test_results_fmt.get(file, 0) // 3
    nonfmt_count = test_results_nonfmt.get(file, 0) // 3
    total_count = fmt_count + nonfmt_count
    print(f"{file}: Total = {total_count}, FMT = {fmt_count}, non-FMT = {nonfmt_count}")
