import os
import sqlite3
import pandas as pd
import re

def count_db_records(db_path):
    """Count records from all LOG_# tables in the database."""
    total_records = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name LIKE 'LOG_%'
        """)
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            total_records += cursor.fetchone()[0] or 0
        
        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
    
    return total_records

def count_txt_frames(txt_path):
    """Count lines that start with 'frame:' in the text file."""
    if not os.path.exists(txt_path):
        return 0
    
    frame_count = 0
    encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-16', 'utf-16-le', 'utf-16-be']
    
    for encoding in encodings:
        try:
            with open(txt_path, 'r', encoding=encoding, errors='ignore') as f:
                for line in f:
                    line_stripped = line.strip()
                    if line_stripped.startswith('frame:'):
                        frame_count += 1
            if frame_count > 0:
                break
            if encoding != encodings[-1]:
                frame_count = 0
        except (UnicodeDecodeError, UnicodeError):
            frame_count = 0
            continue
        except Exception as e:
            frame_count = 0
            continue
    
    return frame_count

def get_base_filename(filename):
    """Extract base filename without extension and timestamp."""
    base = os.path.splitext(filename)[0]
    base = re.sub(r'_\d{8}_\d{6}$', '', base)
    return base

def process_files(directory):
    """Process all .db and .txt files in the directory."""
    results = []
    
    db_files = {}
    txt_files = {}
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if not os.path.isfile(file_path):
            continue
        
        base_name = get_base_filename(filename)
        
        if filename.endswith(".db"):
            db_files[base_name] = file_path
        elif filename.endswith(".txt"):
            txt_files[base_name] = file_path
    
    all_base_names = set(db_files.keys()) | set(txt_files.keys())
    
    for base_name in sorted(all_base_names):
        db_path = db_files.get(base_name)
        txt_path = txt_files.get(base_name)
        
        db_count = count_db_records(db_path) if db_path else 0
        txt_count = count_txt_frames(txt_path) if txt_path else 0
        
        if db_path or txt_path:
            results.append({
                "File": base_name,
                "FLARE (DB)": db_count,
                "Orangebox (TXT)": txt_count,
                "Difference": db_count - txt_count
            })
    
    return results

def main():
    directory_path = "./result/Betaflight/"
    
    if not os.path.exists(directory_path):
        print(f"Directory not found: {directory_path}")
        return
    
    results = process_files(directory_path)
    
    if not results:
        print("No files found to process.")
        return
    
    df = pd.DataFrame(results)
    
    frag50_files = df[df['File'].str.startswith('Frag50')]
    other_files = df[~df['File'].str.startswith('Frag50')]
    
    print("\n=== Betaflight Records Comparison ===")
    
    if not other_files.empty:
        print("\n--- Individual Files ---")
        print(other_files.to_string(index=False))
    
    if not frag50_files.empty:
        print("\n--- Frag50 Files (Average ± Std Dev) ---")
        frag50_count = len(frag50_files)
        print(f"Frag50 files: {frag50_count} files")
        
        for col in ['FLARE (DB)', 'Orangebox (TXT)', 'Difference']:
            if col in frag50_files.columns:
                mean_val = frag50_files[col].mean()
                std_val = frag50_files[col].std()
                min_val = frag50_files[col].min()
                max_val = frag50_files[col].max()
                print(f"{col}: {mean_val:.2f} ± {std_val:.2f} (Range: {min_val} ~ {max_val})")
    
    print("\n=== Summary ===")
    print(f"Total files processed: {len(results)}")
    print(f"Total FLARE records: {df['FLARE (DB)'].sum()}")
    print(f"Total Orangebox records: {df['Orangebox (TXT)'].sum()}")
    print(f"Total difference: {df['Difference'].sum()}")

if __name__ == "__main__":
    main()
