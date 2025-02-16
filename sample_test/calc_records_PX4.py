import os
import sqlite3
import pandas as pd
from datetime import datetime

def count_db_records(db_path):
    total_records = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('info_messages', 'logged_string_message');")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            total_records += cursor.fetchone()[0] or 0

        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")

    return total_records

def count_csv_rows(folder_path):
    total_rows = 0
    try:
        for file in os.listdir(folder_path):
            if file.endswith(".csv"):
                file_path = os.path.join(folder_path, file)
                df = pd.read_csv(file_path)
                total_rows += len(df)
    except Exception as e:
        print(f"Error processing {folder_path}: {e}")

    return total_rows

def process_files(directory):
    results = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".db"):
                record_count = count_db_records(file_path)
                results.append((file, "DB Total Records", record_count))

        for dir in dirs:
            folder_path = os.path.join(root, dir)
            csv_total = count_csv_rows(folder_path)
            results.append((dir, "CSV Total Rows", csv_total))

    return results

directory_path = "./result/PX4/"
results = process_files(directory_path)

# Print Result
df = pd.DataFrame(results, columns=["File Name", "Type", "Count"])
print(df.to_string(index=False))
