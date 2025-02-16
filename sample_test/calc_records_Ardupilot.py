import os
import sqlite3
import re
import pandas as pd
from datetime import datetime

def count_db_records(db_path):
    total_seq_value = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';")
        sequence_table = cursor.fetchone()

        if sequence_table:
            cursor.execute("SELECT SUM(seq) FROM sqlite_sequence;")
            total_seq_value = cursor.fetchone()[0] or 0

        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")

    return total_seq_value

def count_matching_lines(txt_path):
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{2}.*$')
    match_count = 0

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                if pattern.match(line.strip()):
                    match_count += 1
    except Exception as e:
        print(f"Error processing {txt_path}: {e}")

    return match_count

def process_files(directory):
    results = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".db"):
                record_count = count_db_records(file_path)
                results.append((file, "DB Sequence Sum", record_count))
            elif file.endswith(".txt"):
                match_count = count_matching_lines(file_path)
                results.append((file, "Matching Lines", match_count))

    return results

directory_path = "./result/Ardupilot/"
results = process_files(directory_path)

# Print Result
df = pd.DataFrame(results, columns=["File Name", "Type", "Count"])
print(df.to_string(index=False))
