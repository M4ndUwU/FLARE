import os

def find_strings_with_prefix(directory, target_prefixes, target_strings):
    """Searches for target strings preceded by 0x00 0x41 and three unknown bytes, extracts all occurrences of the preceding 2 bytes."""
    results = {}

    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return results

    for filename in os.listdir(directory):
        if not any(filename.startswith(prefix) for prefix in target_prefixes):
            continue

        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'rb') as file:
                data = file.read()
                matches = {}

                for target in target_strings:
                    index = 0
                    while index < len(data):
                        index = data.find(target.encode(), index)
                        if index == -1:
                            break

                        if index >= 5 and data[index - 5] == 0x00 and data[index - 4] == 0x41:
                            preceding_bytes = data[index - 2:index].hex()
                            if target not in matches:
                                matches[target] = []
                            matches[target].append(preceding_bytes)

                        index += len(target)

                if matches:
                    results[filename] = matches

    return results

def count_modified_sequences(directory, prefix_map, combined_results):
    """Counts occurrences of 0x00 0x44 + extracted 2-byte sequences (big-endian) in relevant files."""
    results = {}

    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return results

    for prefix, suffix in prefix_map.items():
        relevant_files = [f for f in os.listdir(directory) if f.endswith(suffix)]

        if prefix in combined_results and combined_results[prefix]:
            sequences = [bytes([0x00, 0x44]) + bytes.fromhex(seq) for seq in combined_results[prefix] if len(seq) == 4]
            for filename in relevant_files:
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    with open(filepath, 'rb') as file:
                        data = file.read()
                        total_count = sum(data.count(seq) for seq in sequences)
                        results[filename] = total_count

    return results

# Define directories
db_dir = "./test/PX4/"
test_dir = "./test/PX4/"
target_prefixes = ["intact_a", "intact_b", "intact_c"]
target_strings = ['battery_status', 'event', 'home_position', 'input_rc', 'position_setpoint_triplet',
                  'sensor_gps', 'vehicle_global_position', 'vehicle_gps_position', 'vehicle_land_detected',
                  'vehicle_local_position', 'vehicle_global_position_groundtruth']

# Search for occurrences
px4_results = find_strings_with_prefix(db_dir, target_prefixes, target_strings)

#Manual Selection !!!!
px4_results = {'intact_a.ulg': {'battery_status': ['4700'], 'event': ['5900'], 'home_position': ['0700'], 'input_rc': ['0800'], 'position_setpoint_triplet': ['0d00'], 'sensor_gps': ['4a00'], 'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'vehicle_land_detected': ['2000'], 'vehicle_local_position': ['2100'], 'vehicle_global_position_groundtruth': ['5600']},
'intact_b.ulg': {'battery_status': ['4700'], 'event': ['5900'], 'home_position': ['0700'], 'input_rc': ['0800'], 'position_setpoint_triplet': ['0d00'], 'sensor_gps': ['4a00', '4b00'], 'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'vehicle_land_detected': ['2000'], 'vehicle_local_position': ['2100'], 'vehicle_global_position_groundtruth': ['5600']},
'intact_c.ulg': {'battery_status': ['4700'], 'event': ['5900'], 'home_position': ['0700'], 'input_rc': ['0800'], 'position_setpoint_triplet': ['0d00'], 'sensor_gps': ['4a00', '4b00'], 'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'vehicle_land_detected': ['2000'], 'vehicle_local_position': ['2100'], 'vehicle_global_position_groundtruth': ['5600']}}

px4_results = {'intact_a.ulg': {'home_position': ['0700'], 'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'sensor_gps': ['4a00'], 'vehicle_global_position_groundtruth': ['5600']},
'intact_b.ulg': {'home_position': ['0700'],  'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'sensor_gps': ['4a00'], 'vehicle_global_position_groundtruth': ['5600']},
'intact_c.ulg': {'home_position': ['0700'], 'vehicle_global_position': ['5f00'], 'vehicle_gps_position': ['1f00'], 'sensor_gps': ['4a00'], 'vehicle_global_position_groundtruth': ['5600']}}


# Combine extracted sequences
combined_results = {"intact_a": set(), "intact_b": set(), "intact_c": set(), "mix": set()}
for file, matches in px4_results.items():
    for key, values in matches.items():
        for prefix in combined_results:
            if file.startswith(prefix):
                combined_results[prefix].update(values)
                combined_results["mix"].update(values)


# Define relevant file mappings
prefix_map = {
    "intact_a": "_a.bin",
    "intact_b": "_b.bin",
    "intact_c": "_c.bin",
    "mix": "mix_"
}

# Count occurrences in test directory
test_results = count_modified_sequences(test_dir, prefix_map, combined_results)

# Print results
print("\nByte Sequence Count in ./test/PX4/:")
for file, total_count in test_results.items():
    print(f"{file}: {total_count}")
