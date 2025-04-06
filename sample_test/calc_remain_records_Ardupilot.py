import os
import sqlite3

def get_fmt_types(db_path, target_names):
    """Fetches (Name, Type, Length) from FMT and returns { type_val: (length_val, name_str) }."""
    result = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = f"""
            SELECT Name, Type, Length
            FROM FMT
            WHERE Name IN ({','.join(['?'] * len(target_names))})
        """
        cursor.execute(query, target_names)
        for row in cursor.fetchall():
            name, t_val, length_val = row
            t_val = int(t_val)
            length_val = int(length_val)
            result[t_val] = (length_val, name)
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
    finally:
        conn.close()
    return result

def parse_messages_strict_next_header(data, all_dict):
    """Parses data with length check and requires next two bytes to be A3 95."""
    i = 0
    data_len = len(data)
    counts = {}

    while i < data_len - 2:
        if data[i] == 0xA3 and data[i+1] == 0x95:
            msg_type = data[i+2]
            if msg_type in all_dict:
                length, name_str = all_dict[msg_type]
                end_pos = i + length
                if end_pos <= data_len and (end_pos + 1) < data_len:
                    if data[end_pos] == 0xA3 and data[end_pos + 1] == 0x95:
                        key = (msg_type, name_str)
                        counts[key] = counts.get(key, 0) + 1
                        i += length
                        continue
        i += 1

    return counts

def main():
    db_dir = "./result/Ardupilot/"
    test_dir = "./test/Ardupilot/"
    target_prefixes = ["intact_a_", "intact_b_", "intact_c_"]
    target_names = [
        'FMT','ADSB','AHR2','AIS1','AIS4','ARSP','BAT','BCL','CAM','CMD','DSTL',
        'EAHR','EV','FNCE','GPS','IMU','MOTB','OABR','OADJ','OAVG','ORGN','POS',
        'RALY','TRIG','TRST'
    ]

    db_files = [
        f for f in os.listdir(db_dir)
        if any(f.startswith(p) for p in target_prefixes) and f.endswith(".db")
    ]

    # Combine all DB info into a single dict.
    all_dict_global = {}
    for db_file in db_files:
        db_path = os.path.join(db_dir, db_file)
        d = get_fmt_types(db_path, target_names)
        for t_val, (length_val, name_str) in d.items():
            all_dict_global[t_val] = (length_val, name_str)

    if not os.path.exists(test_dir):
        print(f"Directory not found: {test_dir}")
        return

    results = {}
    for filename in os.listdir(test_dir):
        filepath = os.path.join(test_dir, filename)
        if os.path.isfile(filepath):
            with open(filepath, "rb") as f:
                data = f.read()
            counts = parse_messages_strict_next_header(data, all_dict_global)
            # Sum only non-FMT
            nonfmt_count = sum(
                c for ((_, name_str), c) in counts.items() if name_str != "FMT"
            )
            results[filename] = nonfmt_count

    print("=== Non-FMT Message Count Per File ===")
    for f in sorted(results.keys()):
        print(f"{f}: {results[f]}")
    print("======================================")

if __name__ == "__main__":
    main()
