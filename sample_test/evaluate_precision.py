#!/usr/bin/env python3
"""
Precision evaluation script for FLARE recovery system.
Compares field values between intact and recovered databases.
"""

import os
import sqlite3
import pandas as pd
import argparse
from collections import Counter

def normalize_value(value):
    """Normalize value for comparison: round floats to 5 decimal places."""
    if value is None:
        return None
    try:
        float_val = float(value)
        return round(float_val, 5)
    except (ValueError, TypeError):
        return str(value)

def get_table_fields(db_path, table_name, firmware_type=None):
    """Get all field values from a table as (field_name, value) tuples."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns_info = cursor.fetchall()
    excluded_columns = ['row_id', 'id']
    
    if firmware_type == "Betaflight":
        excluded_columns.extend(['flightModeFlags', 'stateFlags', 'failsafePhase', 'rxSignalReceived', 'rxFlightChannelsValid'])
    
    columns = [col[1] for col in columns_info if col[1] not in excluded_columns]
    
    if not columns:
        conn.close()
        return []
    
    columns_str = ', '.join([f"`{col}`" for col in columns])
    cursor.execute(f"SELECT {columns_str} FROM `{table_name}`")
    rows = cursor.fetchall()
    
    field_values = []
    for row in rows:
        for col, value in zip(columns, row):
            if value is not None:
                normalized_value = normalize_value(value)
                field_values.append((col, normalized_value))
    
    conn.close()
    return field_values

def compare_databases_field_level(intact_db, recovered_db, firmware_type):
    """Compare databases at field level. Returns (tp, fp)."""
    intact_conn = sqlite3.connect(intact_db)
    recovered_conn = sqlite3.connect(recovered_db)
    
    intact_cursor = intact_conn.cursor()
    recovered_cursor = recovered_conn.cursor()
    
    if firmware_type == "Ardupilot":
        intact_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name != 'FMT'
            AND name != 'sqlite_sequence'
        """)
        recovered_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name != 'FMT'
            AND name != 'sqlite_sequence'
        """)
    elif firmware_type == "PX4":
        intact_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT IN ('info_messages', 'logged_string_message', 'sqlite_sequence')
        """)
        recovered_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT IN ('info_messages', 'logged_string_message', 'sqlite_sequence')
        """)
    elif firmware_type == "Betaflight":
        intact_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT IN ('headers', 'events', 'sqlite_sequence')
            AND name LIKE 'LOG_%'
        """)
        recovered_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT IN ('headers', 'events', 'sqlite_sequence')
            AND name LIKE 'LOG_%'
        """)
    
    intact_tables = {row[0] for row in intact_cursor.fetchall()}
    recovered_tables = {row[0] for row in recovered_cursor.fetchall()}
    
    intact_conn.close()
    recovered_conn.close()
    
    if firmware_type == "Betaflight":
        intact_fields = Counter()
        recovered_fields = Counter()
        
        for table_name in intact_tables:
            field_values = get_table_fields(intact_db, table_name, firmware_type)
            for field, value in field_values:
                intact_fields[(field, value)] += 1
        
        for table_name in recovered_tables:
            field_values = get_table_fields(recovered_db, table_name, firmware_type)
            for field, value in field_values:
                recovered_fields[(field, value)] += 1
        
        common_keys = set(intact_fields.keys()) & set(recovered_fields.keys())
        tp = sum(min(intact_fields[k], recovered_fields[k]) for k in common_keys)
        
        fp_by_column = Counter()
        for k in recovered_fields.keys():
            fp_count = max(0, recovered_fields[k] - intact_fields.get(k, 0))
            if fp_count > 0:
                field = k[0]
                fp_by_column[field] += fp_count
        
        fp = sum(fp_by_column.values())
        
        return tp, fp
        
    else:
        intact_fields = Counter()
        recovered_fields = Counter()
        
        px4_table_mapping = {
            'vehicle_global_position_and_vehicle_global_position_groundtruth': ['vehicle_global_position_0', 'vehicle_global_position_groundtruth_0'],
            'vehicle_gps_position_and_sensor_gps': ['vehicle_gps_position_0', 'sensor_gps_0']
        }
        
        for table_name in intact_tables:
            field_values = get_table_fields(intact_db, table_name, firmware_type)
            for field, value in field_values:
                intact_fields[(table_name, field, value)] += 1
        
        for table_name in recovered_tables:
            field_values = get_table_fields(recovered_db, table_name, firmware_type)
            
            if firmware_type == "PX4" and table_name in px4_table_mapping:
                mapped_tables = px4_table_mapping[table_name]
                for mapped_table in mapped_tables:
                    if mapped_table in intact_tables:
                        for field, value in field_values:
                            recovered_fields[(mapped_table, field, value)] += 1
                    else:
                        for field, value in field_values:
                            recovered_fields[(table_name, field, value)] += 1
            else:
                for field, value in field_values:
                    recovered_fields[(table_name, field, value)] += 1
        
        common_keys = set(intact_fields.keys()) & set(recovered_fields.keys())
        tp = sum(min(intact_fields[k], recovered_fields[k]) for k in common_keys)
        
        fp_by_column = Counter()
        for k in recovered_fields.keys():
            fp_count = max(0, recovered_fields[k] - intact_fields.get(k, 0))
            if fp_count > 0:
                table, field = k[0], k[1]
                fp_by_column[field] += fp_count
        
        fp = sum(fp_by_column.values())
    
    return tp, fp

def evaluate_firmware_precision(firmware_type, result_dir):
    """Evaluate precision for a single firmware type."""
    results = []
    
    intact_dbs = []
    for f in os.listdir(result_dir):
        if f.startswith("intact_") and f.endswith(".db"):
            intact_dbs.append(os.path.join(result_dir, f))
    
    frag50_dbs = []
    for f in os.listdir(result_dir):
        if f.startswith("Frag50_") and f.endswith(".db"):
            frag50_dbs.append((f, os.path.join(result_dir, f)))
    
    if not frag50_dbs:
        print(f"No Frag50 files found for {firmware_type}")
        return pd.DataFrame()
    
    for frag50_file, frag50_path in sorted(frag50_dbs):
        print(f"Comparing {frag50_file} with {len(intact_dbs)} intact file(s)...")
        
        if firmware_type in ["Ardupilot", "PX4"]:
            if not intact_dbs:
                print(f"Warning: No intact files found for {firmware_type}")
                continue
            
            all_intact_fields = Counter()
            
            for intact_path in intact_dbs:
                if not os.path.exists(intact_path):
                    continue
                
                try:
                    intact_conn = sqlite3.connect(intact_path)
                    intact_cursor = intact_conn.cursor()
                    
                    if firmware_type == "Ardupilot":
                        intact_cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' 
                            AND name != 'FMT'
                            AND name != 'sqlite_sequence'
                        """)
                    elif firmware_type == "PX4":
                        intact_cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' 
                            AND name NOT IN ('info_messages', 'logged_string_message', 'sqlite_sequence')
                        """)
                    
                    intact_tables = {row[0] for row in intact_cursor.fetchall()}
                    
                    for table_name in intact_tables:
                        field_values = get_table_fields(intact_path, table_name, firmware_type)
                        for field, value in field_values:
                            all_intact_fields[(table_name, field, value)] += 1
                    
                    intact_conn.close()
                except Exception as e:
                    print(f"Error reading {os.path.basename(intact_path)}: {e}")
                    continue
            
            try:
                recovered_conn = sqlite3.connect(frag50_path)
                recovered_cursor = recovered_conn.cursor()
                
                if firmware_type == "Ardupilot":
                    recovered_cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        AND name != 'FMT'
                        AND name != 'sqlite_sequence'
                    """)
                elif firmware_type == "PX4":
                    recovered_cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' 
                        AND name NOT IN ('info_messages', 'logged_string_message', 'sqlite_sequence')
                    """)
                
                recovered_tables = {row[0] for row in recovered_cursor.fetchall()}
                recovered_conn.close()
                
                recovered_fields = Counter()
                px4_table_mapping = {
                    'vehicle_global_position_and_vehicle_global_position_groundtruth': ['vehicle_global_position_0', 'vehicle_global_position_groundtruth_0'],
                    'vehicle_gps_position_and_sensor_gps': ['vehicle_gps_position_0', 'sensor_gps_0']
                }
                
                for table_name in recovered_tables:
                    field_values = get_table_fields(frag50_path, table_name, firmware_type)
                    
                    if firmware_type == "PX4" and table_name in px4_table_mapping:
                        mapped_tables = px4_table_mapping[table_name]
                        for field, value in field_values:
                            mapped_to_any = False
                            for mapped_table in mapped_tables:
                                if (mapped_table, field, value) in all_intact_fields:
                                    recovered_fields[(mapped_table, field, value)] += 1
                                    mapped_to_any = True
                                    break
                            
                            if not mapped_to_any:
                                recovered_fields[(table_name, field, value)] += 1
                    else:
                        for field, value in field_values:
                            recovered_fields[(table_name, field, value)] += 1
                
                common_keys = set(all_intact_fields.keys()) & set(recovered_fields.keys())
                tp = sum(min(all_intact_fields[k], recovered_fields[k]) for k in common_keys)
                
                fp_by_column = Counter()
                for k in recovered_fields.keys():
                    fp_count = max(0, recovered_fields[k] - all_intact_fields.get(k, 0))
                    if fp_count > 0:
                        table, field = k[0], k[1]
                        fp_by_column[field] += fp_count
                
                fp = sum(fp_by_column.values())
                
                if tp + fp > 0:
                    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    
                    results.append({
                        "File": frag50_file,
                        "TP": tp,
                        "FP": fp,
                        "Precision": precision
                    })
            except Exception as e:
                print(f"Error comparing {frag50_file}: {e}")
                continue
        
        elif firmware_type == "Betaflight":
            intact_path = None
            for intact_file in intact_dbs:
                base_frag50 = frag50_file.replace("Frag50_", "").replace(".db", "")
                base_intact = os.path.basename(intact_file).replace("intact_", "").replace(".db", "")
                if base_intact in base_frag50 or base_frag50 in base_intact:
                    intact_path = intact_file
                    break
            
            if not intact_path and intact_dbs:
                intact_path = intact_dbs[0]
            
            if intact_path and os.path.exists(intact_path):
                try:
                    tp, fp = compare_databases_field_level(intact_path, frag50_path, firmware_type)
                    
                    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                    
                    results.append({
                        "File": frag50_file,
                        "TP": tp,
                        "FP": fp,
                        "Precision": precision
                    })
                except Exception as e:
                    print(f"Error comparing {frag50_file}: {e}")
                    continue
    
    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description='Evaluate precision for FLARE recovery system')
    parser.add_argument('--firmware', choices=['Ardupilot', 'Betaflight', 'PX4', 'all'], 
                       default='all', help='Firmware type to evaluate')
    parser.add_argument('--result-dir', default='./result', help='Result files directory')
    
    args = parser.parse_args()
    
    firmware_types = ['Ardupilot', 'Betaflight', 'PX4'] if args.firmware == 'all' else [args.firmware]
    
    all_results = {}
    
    for firmware_type in firmware_types:
        result_dir = os.path.join(args.result_dir, firmware_type)
        
        if not os.path.exists(result_dir):
            print(f"Skipping {firmware_type}: directory not found")
            continue
        
        print(f"\n{'='*60}")
        print(f"Evaluating Precision for {firmware_type}")
        print(f"{'='*60}")
        
        df = evaluate_firmware_precision(firmware_type, result_dir)
        
        if df.empty:
            print(f"No matching files found for {firmware_type}")
            continue
        
        all_results[firmware_type] = df
        
        print(f"\n--- {firmware_type} Frag50 Results ---")
        if not df.empty:
            print("\nIndividual Files:")
            print(df[['File', 'TP', 'FP', 'Precision']].to_string(index=False))
            
            print("\nFrag50 Files (Average ± Std Dev):")
            if 'Precision' in df.columns:
                mean_val = df['Precision'].mean()
                std_val = df['Precision'].std()
                min_val = df['Precision'].min()
                max_val = df['Precision'].max()
                print(f"  Precision: {mean_val:.4f} ± {std_val:.4f} (Range: {min_val:.4f} ~ {max_val:.4f})")
            
            print(f"\nOverall {firmware_type} Summary:")
            print(f"  Average Precision: {df['Precision'].mean():.4f}")
    
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("Cross-Firmware Comparison")
        print(f"{'='*60}")
        comparison_data = []
        for fw_type, df in all_results.items():
            comparison_data.append({
                "Firmware": fw_type,
                "Avg Precision": df['Precision'].mean()
            })
        comparison_df = pd.DataFrame(comparison_data)
        print(comparison_df.to_string(index=False))

if __name__ == "__main__":
    main()
