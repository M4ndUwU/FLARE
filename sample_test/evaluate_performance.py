#!/usr/bin/env python3
"""
Runtime performance evaluation script for FLARE recovery system.
Measures recovery speed (MB/s) for Frag50 files.
"""

import os
import sys
import time
import pandas as pd
import argparse
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.ardupilot_parse.df_parser import df_recover
from modules.px4_parse.ulog_parser import ulog_recover
from modules.betaflight_parse.bbl_parser import bbl_recover

def measure_recovery_speed(file_path, firmware_type, intact_file, cluster_size=8192):
    """Measure recovery speed (MB/s) for a file."""
    temp_dir = tempfile.mkdtemp()
    output_db = os.path.join(temp_dir, "temp_eval.db")
    
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    start_time = time.time()
    success = False
    
    try:
        if firmware_type == "Ardupilot":
            match_types = ['FMT','ADSB','AHR2','AIS1','AIS4','ARSP','BAT','BCL','CAM','CMD','DSTL',
                          'EAHR','EV','FNCE','GPS','IMU','MOTB','OABR','OADJ','OAVG','ORGN','POS',
                          'RALY','TRIG','TRST']
            df_recover(file_path, match_types, intact_file, cluster_size, output_db)
            success = True
        elif firmware_type == "PX4":
            match_types = ['battery_status', 'event', 'home_position', 'input_rc', 'position_setpoint_triplet',
                          'sensor_gps', 'vehicle_global_position', 'vehicle_gps_position', 'vehicle_land_detected',
                          'vehicle_local_position', 'vehicle_global_position_groundtruth']
            ulog_recover(file_path, intact_file, match_types, cluster_size, output_db)
            success = True
        elif firmware_type == "Betaflight":
            bbl_recover(file_path, intact_file, cluster_size, output_db)
            success = True
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        success = False
    finally:
        elapsed_time = time.time() - start_time
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    if success and elapsed_time > 0:
        speed_mbps = file_size_mb / elapsed_time
    else:
        speed_mbps = None
    
    return speed_mbps, success

def evaluate_frag50_speed(firmware_type, test_dir):
    """Measure recovery speed for Frag50 files."""
    results = []
    
    intact_files = {}
    if firmware_type == "Ardupilot":
        for f in os.listdir(test_dir):
            if f.startswith("intact_") and (f.endswith(".BIN") or f.endswith(".bin")):
                label = f.replace("intact_", "").replace(".BIN", "").replace(".bin", "")
                intact_files[label] = os.path.join(test_dir, f)
    elif firmware_type == "PX4":
        for f in os.listdir(test_dir):
            if f.startswith("intact_") and f.endswith(".ulg"):
                label = f.replace("intact_", "").replace(".ulg", "")
                intact_files[label] = os.path.join(test_dir, f)
    elif firmware_type == "Betaflight":
        for f in os.listdir(test_dir):
            if f.startswith("intact_") and (f.endswith(".bbl") or f.endswith(".bin")):
                label = f.replace("intact_", "").replace(".bbl", "").replace(".bin", "")
                intact_files[label] = os.path.join(test_dir, f)
    
    frag50_files = [f for f in os.listdir(test_dir) 
                    if f.startswith("Frag50") and os.path.isfile(os.path.join(test_dir, f))]
    
    for frag50_file in sorted(frag50_files):
        frag50_path = os.path.join(test_dir, frag50_file)
        
        intact_file = None
        for label, intact_path in intact_files.items():
            if label in frag50_file:
                intact_file = intact_path
                break
        
        if not intact_file or not os.path.exists(intact_file):
            print(f"Warning: No intact file found for {frag50_file}, skipping...")
            continue
        
        print(f"Measuring recovery speed for {frag50_file}...")
        
        recovery_speed, recovery_success = measure_recovery_speed(frag50_path, firmware_type, intact_file)
        
        results.append({
            "File": frag50_file,
            "Recovery Speed (MB/s)": recovery_speed if recovery_success else None
        })
    
    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description='Measure runtime performance for Frag50 files')
    parser.add_argument('--firmware', choices=['Ardupilot', 'Betaflight', 'PX4', 'all'], 
                       default='all', help='Firmware type to evaluate')
    parser.add_argument('--test-dir', default='./test', help='Test files directory')
    
    args = parser.parse_args()
    
    firmware_types = ['Ardupilot', 'Betaflight', 'PX4'] if args.firmware == 'all' else [args.firmware]
    
    all_results = {}
    
    for firmware_type in firmware_types:
        test_dir = os.path.join(args.test_dir, firmware_type)
        
        if not os.path.exists(test_dir):
            print(f"Skipping {firmware_type}: directory not found")
            continue
        
        print(f"\n{'='*60}")
        print(f"Measuring Frag50 Speed for {firmware_type}")
        print(f"{'='*60}")
        
        df = evaluate_frag50_speed(firmware_type, test_dir)
        
        if df.empty:
            print(f"No Frag50 files found for {firmware_type}")
            continue
        
        all_results[firmware_type] = df
        
        print(f"\n--- {firmware_type} Frag50 Speed Results ---")
        print(df.to_string(index=False))
        
        if df['Recovery Speed (MB/s)'].notna().any():
            recovery_mean = df['Recovery Speed (MB/s)'].mean()
            recovery_std = df['Recovery Speed (MB/s)'].std()
            recovery_min = df['Recovery Speed (MB/s)'].min()
            recovery_max = df['Recovery Speed (MB/s)'].max()
            print(f"\nRecovery Speed: {recovery_mean:.2f} ± {recovery_std:.2f} MB/s (Range: {recovery_min:.2f} ~ {recovery_max:.2f} MB/s)")
    
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("Cross-Firmware Comparison")
        print(f"{'='*60}")
        comparison_data = []
        for fw_type, df in all_results.items():
            comp_row = {"Firmware": fw_type}
            if df['Recovery Speed (MB/s)'].notna().any():
                comp_row["Avg Recovery Speed (MB/s)"] = df['Recovery Speed (MB/s)'].mean()
            comparison_data.append(comp_row)
        comparison_df = pd.DataFrame(comparison_data)
        print(comparison_df.to_string(index=False))

if __name__ == "__main__":
    main()
