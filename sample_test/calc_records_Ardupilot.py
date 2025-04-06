import os
import sqlite3
import re
import pandas as pd
from datetime import datetime

def count_db_records_excluding_fmt(db_path):
    """
    Returns the sum of 'seq' from the sqlite_sequence table,
    excluding any rows for the 'FMT' table.
    """
    total_seq_value = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if sqlite_sequence table exists
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='sqlite_sequence';
        """)
        sequence_table = cursor.fetchone()

        if sequence_table:
            # Exclude FMT by name
            cursor.execute("""
                SELECT SUM(seq)
                FROM sqlite_sequence
                WHERE name <> 'FMT';
            """)
            total_seq_value = cursor.fetchone()[0] or 0

        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")

    return total_seq_value

def count_matching_lines_excluding_fmt(txt_path):
    """
    Counts lines that start with a timestamp format:
      YYYY-MM-DD HH:MM:SS.xx
    but excludes lines that contain 'FMT'.
    """
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{2}.*$')
    match_count = 0

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_stripped = line.strip()
                # Check if line matches the timestamp pattern
                if pattern.match(line_stripped):
                    # Exclude if it contains 'FMT'
                    if 'FMT' not in line_stripped:
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
                # Count DB records excluding FMT
                record_count = count_db_records_excluding_fmt(file_path)
                results.append((file, "DB Sequence Sum (Excl. FMT)", record_count))
            elif file.endswith(".txt"):
                # Count lines excluding 'FMT'
                match_count = count_matching_lines_excluding_fmt(file_path)
                results.append((file, "Matching Lines (Excl. FMT)", match_count))

    return results

def main():
    directory_path = "./result/Ardupilot/"
    results = process_files(directory_path)

    df = pd.DataFrame(results, columns=["File Name", "Type", "Count"])
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
