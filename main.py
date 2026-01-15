import argparse, os
import sqlite3
import json
import webbrowser
import hashlib
from datetime import datetime
from modules.ardupilot_parse.df_parser import df_parser, df_recover
from modules.betaflight_parse.bbl_parser import bbl_parser, bbl_recover
from modules.px4_parse.ulog_parser import ulog_parser, ulog_recover

def detect_type_read_file_header(log_file):
    MAX_LEN_HEADER = 16
    ULOG_HEADER_BYTES = b'\x55\x4c\x6f\x67\x01\x12\x35'
    DATAFLASH_HEADER_BYTES = b'\xA3\x95\x80'
    BBL_HEADER_BYTES = b'\x48\x20\x50\x72\x6f\x64\x75\x63\x74\x3a\x42\x6c\x61\x63\x6b\x62\x6f\x78\x20\x66\x6c\x69\x67\x68\x74\x20\x64\x61\x74\x61\x20\x72\x65\x63\x6f\x72\x64\x65\x72\x20\x62\x79\x20\x4e\x69\x63\x68\x6f\x6c\x61\x73\x20\x53\x68\x65\x72\x6c\x6f\x63\x6b\x0a'

    file_handle = open(log_file, "rb")
    header_data = file_handle.read(MAX_LEN_HEADER)
    file_handle.close()

    if len(header_data) != MAX_LEN_HEADER:
        raise TypeError("Invalid file format (Header too short)")

    if header_data[:7] == ULOG_HEADER_BYTES:
        return "PX4-ULog File"
    elif header_data[:3] == DATAFLASH_HEADER_BYTES:
        return "Ardupilot-DataFlash File"
    elif header_data[:MAX_LEN_HEADER] == BBL_HEADER_BYTES[:MAX_LEN_HEADER]:
        return "Betaflight/Cleanflight-Blackbox File"
    else:
        raise TypeError("Invalid file format (Neither ULOG nor DataFlash nor Betaflight/Cleanflight)")

def get_match_types(type):
    if type == "PX4-ULog File":
        match_types = ['battery_status', 'event', 'home_position', 'input_rc', 'position_setpoint_triplet', 'sensor_gps', 'vehicle_global_position', 'vehicle_global_position_groundtruth', 'vehicle_gps_position', 'vehicle_land_detected', 'vehicle_local_position']
    elif type == "Betaflight/Cleanflight-Blackbox File":
        match_types = []
    elif type == "Ardupilot-DataFlash File":
        match_types = ['FMT', 'ADSB', 'AHR2', 'AIS1', 'AIS4', 'ARSP', 'BAT', 'BCL', 'CAM', 'CMD', 'DSTL', 'EAHR', 'EV', 'FNCE', 'GPS', 'IMU', 'MOTB', 'OABR', 'OADJ', 'OAVG', 'ORGN', 'POS', 'RALY', 'TRIG', 'TRST']

    return match_types

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()



def main():
    """Commande line interface"""
    parser = argparse.ArgumentParser(
        description='Parsing the flight log files of a open-source drone, recovering any deleted sections if present, and saving the parsed data into a database.'
    )
    parser.add_argument('filename', metavar='file.bin', help='Input fragment of the log file to be recovered')
    #parser.add_argument("--types", default=None, help="types of messages (comma separated with wildcard)")
    parser.add_argument('-r', '--recovery', action='store_true', help='Enable recovery mode')
    parser.add_argument('-i', '--intact_filename', metavar='file.ulg', help='Input intact log file (optional in recovery mode)', default=None)
    parser.add_argument('-f', '--firmware', choices=['ardupilot', 'px4', 'betaflight'], help='Firmware type (required if intact log is not provided in recovery mode)', default=None)
    parser.add_argument('-o', '--output', dest='output', action='store', required=True, help='Output path of DB file')
    parser.add_argument('-c', '--cluster_size', type=int, default=8192, help='Cluster size for parsing (default is 8192)')
    parser.add_argument('-v', '--view', action='store_true', help='Generate an HTML report and open it in a web browser.')
    parser.add_argument('--google-maps-key', dest='google_maps_key', help='Google Maps API key for enhanced map visualization (or set GOOGLE_MAPS_API_KEY environment variable)')
    # Validate that either intact_filename or firmware is provided
    args = parser.parse_args()


    log_file_name = args.filename
    
    # Calculate SHA256 hash before analysis
    print("=" * 60)
    print("Calculating SHA256 hash of input file before analysis...")
    try:
        hash_before = calculate_sha256(log_file_name)
        print(f"SHA256 (before analysis): {hash_before}")
    except Exception as e:
        print(f"Error calculating SHA256 hash before analysis: {e}")
        hash_before = None
    
    # Remove the path and file extension from the filename.
    base_filename = os.path.splitext(os.path.basename(log_file_name))[0]
    # Add the current timestamp.
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    new_filename = f"{base_filename}_{timestamp}.db"
    # Combine the output path with the new filename.
    output = os.path.join(args.output, new_filename)


    # Ensure filename is always required in recovery mode
    if args.recovery:
        if not args.intact_filename and not args.firmware:
            parser.error('In recovery mode, either intact_filename must be provided or firmware type must be specified.')

        if args.intact_filename:
            orig_log_file_name = args.intact_filename
            type = detect_type_read_file_header(orig_log_file_name)
            print(orig_log_file_name + " is " + type + ".")
        elif args.firmware:
            orig_log_file_name = None
            if args.firmware == 'ardupilot':
                type = "Ardupilot-DataFlash File"
            elif args.firmware == 'px4':
                type = "PX4-ULog File"
            elif args.firmware == 'betaflight':
                type = "Betaflight/Cleanflight-Blackbox File"
            else:
                return
            print("Selected " + type + ".")
    else:
        type = detect_type_read_file_header(log_file_name)
        print(log_file_name + " is " + type + ".")

    if type == "PX4-ULog File":
        match_types = get_match_types(type)
        print("Progressing...")
        if args.recovery:
            ulog_recover(log_file_name, orig_log_file_name, match_types, args.cluster_size, output)
        else:
            ulog_parser(log_file_name, match_types, output)
    elif type == "Betaflight/Cleanflight-Blackbox File":
        print("Progressing...")
        if args.recovery:
            bbl_recover(log_file_name, orig_log_file_name, args.cluster_size, output)
        else:
            bbl_parser(log_file_name, output)
    elif type == "Ardupilot-DataFlash File":
        match_types = get_match_types(type)
        print("Progressing...")
        if args.recovery:
            df_recover(log_file_name, match_types, orig_log_file_name, args.cluster_size, output)
        else:
            df_parser(log_file_name, match_types, output)
    print("Finished. Result is in " + output)
    
    # Calculate SHA256 hash after analysis
    print("=" * 60)
    print("Calculating SHA256 hash of input file after analysis...")
    try:
        hash_after = calculate_sha256(log_file_name)
        print(f"SHA256 (after analysis):  {hash_after}")
    except Exception as e:
        print(f"Error calculating SHA256 hash after analysis: {e}")
        hash_after = None
    
    # Compare hashes
    print("=" * 60)
    print("Hash Comparison Result:")
    if hash_before is not None and hash_after is not None:
        if hash_before == hash_after:
            print("Status: MATCH - File integrity verified (file unchanged)")
            print(f"Both hashes: {hash_before}")
        else:
            print("Status: MISMATCH - File was modified during analysis")
            print(f"Hash before: {hash_before}")
            print(f"Hash after:  {hash_after}")
    else:
        print("Status: ERROR - Could not complete hash comparison")
    print("=" * 60)

    if args.view:
        html_report_path = os.path.splitext(output)[0] + '.html'
        
        # Check for Google Maps API key from multiple sources
        google_maps_key = args.google_maps_key or os.environ.get('GOOGLE_MAPS_API_KEY')
        
        # If still not found, try to load from config file
        if not google_maps_key:
            try:
                config_path = os.path.join(os.path.dirname(__file__), 'config.json')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        google_maps_key = config.get('google_maps_api_key')
                        if google_maps_key and google_maps_key != "YOUR_GOOGLE_MAPS_API_KEY_HERE":
                            print("✓ Loaded Google Maps API key from config.json")
            except Exception as e:
                print(f"Warning: Could not load config.json: {e}")
        
        generate_html_report(output, html_report_path, args.recovery, google_maps_key)
        print(f"HTML report generated: {html_report_path}")
        
        if google_maps_key:
            print("✓ Using Google Maps API for enhanced visualization")
        else:
            print("⚠ Using default map (Google Maps API key not provided)")
            print("   To enable Google Maps, set GOOGLE_MAPS_API_KEY environment variable or use --google-maps-key")
        
        try:
            webbrowser.open(f'file://{os.path.abspath(html_report_path)}')
            print("Opening HTML report in web browser...")
        except Exception as e:
            print(f"Could not open browser automatically: {e}")
            print(f"Please open the file manually: {html_report_path}")

    return output

def safe_float(value, default=0.0):
    """Safely convert value to float, handling None, empty strings, and invalid values"""
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value or value == '':
            return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def generate_html_report(db_path, html_path, is_recovery_mode=False, google_maps_api_key=None):
    """Generate HTML report with map and table visualization of GPS data"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get database type by checking available tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    gps_data = []
    firmware_type = "Unknown"
    columns = ["Timestamp", "Latitude", "Longitude", "Altitude", "Speed"]
    
    # Check if it's Ardupilot (GPS table)
    if 'GPS' in tables:
        try:
            cursor.execute("""
                SELECT timestamp, Lat, Lng, Alt, Spd 
                FROM GPS 
                WHERE Lat IS NOT NULL AND Lng IS NOT NULL
                ORDER BY timestamp
            """)
            gps_data = cursor.fetchall()
            if gps_data:
                firmware_type = "Ardupilot"
                columns = ["Timestamp", "Latitude", "Longitude", "Altitude", "Speed"]
        except sqlite3.OperationalError:
            pass
        
    # Check if it's Betaflight (LOG_# tables)
    if not gps_data and any(table.startswith('LOG_') for table in tables):
        log_tables = [table for table in tables if table.startswith('LOG_')]
        print(f"Checking Betaflight tables: {log_tables}")
        for table in log_tables:
            try:
                # Get table schema to find actual column names
                cursor.execute(f"PRAGMA table_info(`{table}`)")
                columns_info = cursor.fetchall()
                column_names = [col[1] for col in columns_info]
                print(f"Table {table} columns: {column_names}")
                
                # Find GPS-related columns
                time_col = None
                lat_col = None
                lng_col = None
                alt_col = None
                speed_col = None
                
                # Find time column
                for col in column_names:
                    if any(x in col.lower() for x in ['time', 'timestamp']):
                        time_col = col
                        break
                
                # Find GPS coordinate columns - try different patterns
                # Betaflight can have various GPS column names depending on firmware version
                for col in column_names:
                    col_lower = col.lower()
                    # Check for GPS_coord[0] or GPS_coord[1] pattern (most common)
                    if 'gps_coord' in col_lower and '[0]' in col:
                        lat_col = col
                    elif 'gps_coord' in col_lower and '[1]' in col:
                        lng_col = col
                    # Check for GPS_lat, GPS_lon
                    elif 'gps_lat' in col_lower:
                        lat_col = col
                    elif 'gps_lon' in col_lower:
                        lng_col = col
                    # Check for other GPS coordinate patterns
                    elif 'gps' in col_lower and 'lat' in col_lower:
                        lat_col = col
                    elif 'gps' in col_lower and ('lon' in col_lower or 'lng' in col_lower):
                        lng_col = col
                
                # Find altitude and speed columns
                for col in column_names:
                    col_lower = col.lower()
                    if not alt_col and 'gps' in col_lower and 'alt' in col_lower:
                        alt_col = col
                    elif not alt_col and 'alt' in col_lower:
                        alt_col = col
                    if not speed_col and 'gps' in col_lower and any(x in col_lower for x in ['speed', 'vel', 'spd']):
                        speed_col = col
                    elif not speed_col and any(x in col_lower for x in ['speed', 'vel', 'spd']):
                        speed_col = col
                
                print(f"Found columns - time: {time_col}, lat: {lat_col}, lng: {lng_col}, alt: {alt_col}, speed: {speed_col}")
                
                # If we found time, lat, and lng, try to query
                if time_col and lat_col and lng_col:
                    # Always use backticks for all column names to handle special characters
                    time_col_quoted = f"`{time_col}`"
                    lat_col_quoted = f"`{lat_col}`"
                    lng_col_quoted = f"`{lng_col}`"
                    alt_col_quoted = f"`{alt_col}`" if alt_col else 'NULL'
                    speed_col_quoted = f"`{speed_col}`" if speed_col else 'NULL'
                    
                    query = f"""
                        SELECT {time_col_quoted}, {lat_col_quoted}, {lng_col_quoted}, {alt_col_quoted}, {speed_col_quoted}
                        FROM `{table}`
                        WHERE {lat_col_quoted} IS NOT NULL AND {lng_col_quoted} IS NOT NULL
                        ORDER BY CAST({time_col_quoted} AS INTEGER) ASC
                    """
                    
                    print(f"Executing query: {query[:200]}...")
                    cursor.execute(query)
                    table_data = cursor.fetchall()
                    if table_data:
                        gps_data.extend(table_data)
                        firmware_type = "Betaflight"
                        columns = ["Time (usec)", "Latitude", "Longitude", "Altitude", "Speed"]
                        print(f"Found {len(table_data)} GPS data points in table {table}")
                        break
                    else:
                        print(f"No GPS data found in table {table} (query succeeded but returned no rows)")
                else:
                    print(f"Missing required columns in table {table}: time={time_col}, lat={lat_col}, lng={lng_col}")
            except sqlite3.OperationalError as e:
                print(f"Error querying table {table}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error with table {table}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if gps_data:
            print(f"Found {len(gps_data)} total GPS data points from Betaflight tables")
        
    # Check if it's PX4 (vehicle_gps_position_0 table)
    if not gps_data and 'vehicle_gps_position_0' in tables:
        try:
            cursor.execute("""
                SELECT timestamp, latitude_deg, longitude_deg, altitude_msl_m, vel_m_s 
                FROM vehicle_gps_position_0 
                WHERE latitude_deg IS NOT NULL AND longitude_deg IS NOT NULL
                ORDER BY CAST(timestamp AS INTEGER) ASC
            """)
            gps_data = cursor.fetchall()
            if gps_data:
                firmware_type = "PX4"
                columns = ["Timestamp (usec)", "Latitude", "Longitude", "Altitude (MSL)", "Velocity (m/s)"]
        except sqlite3.OperationalError:
            pass
    
    # Generic GPS data search if no specific firmware detected
    if not gps_data:
        print("No specific firmware detected, searching for GPS data in all tables...")
        for table in tables:
            try:
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table})")
                columns_info = cursor.fetchall()
                column_names = [col[1] for col in columns_info]
                
                # Look for common GPS column patterns
                lat_cols = [col for col in column_names if 'lat' in col.lower()]
                lng_cols = [col for col in column_names if any(x in col.lower() for x in ['lng', 'lon', 'long'])]
                time_cols = [col for col in column_names if any(x in col.lower() for x in ['time', 'timestamp'])]
                alt_cols = [col for col in column_names if any(x in col.lower() for x in ['alt', 'height'])]
                speed_cols = [col for col in column_names if any(x in col.lower() for x in ['speed', 'vel', 'spd'])]
                
                if lat_cols and lng_cols and time_cols:
                    lat_col = lat_cols[0]
                    lng_col = lng_cols[0]
                    time_col = time_cols[0]
                    alt_col = alt_cols[0] if alt_cols else 'NULL'
                    speed_col = speed_cols[0] if speed_cols else 'NULL'
                    
                    # Use backticks for column names that might have special characters
                    lat_col_quoted = f"`{lat_col}`" if '[' in lat_col or ' ' in lat_col else lat_col
                    lng_col_quoted = f"`{lng_col}`" if '[' in lng_col or ' ' in lng_col else lng_col
                    time_col_quoted = f"`{time_col}`" if '[' in time_col or ' ' in time_col else time_col
                    alt_col_quoted = f"`{alt_col}`" if alt_col != 'NULL' and ('[' in alt_col or ' ' in alt_col) else alt_col
                    speed_col_quoted = f"`{speed_col}`" if speed_col != 'NULL' and ('[' in speed_col or ' ' in speed_col) else speed_col
                    
                    query = f"""
                        SELECT {time_col_quoted}, {lat_col_quoted}, {lng_col_quoted}, {alt_col_quoted}, {speed_col_quoted}
                        FROM `{table}`
                        WHERE {lat_col_quoted} IS NOT NULL AND {lng_col_quoted} IS NOT NULL
                        ORDER BY {time_col_quoted}
                    """
                    
                    cursor.execute(query)
                    table_data = cursor.fetchall()
                    if table_data:
                        gps_data.extend(table_data)
                        firmware_type = f"Generic ({table})"
                        columns = ["Timestamp", "Latitude", "Longitude", "Altitude", "Speed"]
                        print(f"Found GPS data in table: {table}")
                        break
                        
            except sqlite3.OperationalError:
                continue
    
    conn.close()
    
    if not gps_data:
        raise ValueError("No GPS data found in the database")
    
    # Convert data for JavaScript
    map_points = []
    table_rows = []
    
    for row in gps_data:
        if firmware_type == "Ardupilot":
            timestamp, lat, lng, alt, spd = row
            # Convert to float for formatting, handle None and empty string values
            lat_float = safe_float(lat)
            lng_float = safe_float(lng)
            alt_float = safe_float(alt)
            spd_float = safe_float(spd)
            
            map_points.append({
                'lat': lat_float,
                'lng': lng_float,
                'timestamp': str(timestamp) if timestamp else '',
                'altitude': alt_float,
                'speed': spd_float
            })
            table_rows.append([str(timestamp), f"{lat_float:.6f}", f"{lng_float:.6f}", f"{alt_float:.2f}", f"{spd_float:.2f}"])
            
        elif firmware_type == "Betaflight":
            time, lat, lng, alt, spd = row
            # Convert to float for formatting, handle None and empty string values
            lat_float = safe_float(lat)
            lng_float = safe_float(lng)
            alt_float = safe_float(alt)
            spd_float = safe_float(spd)
            
            map_points.append({
                'lat': lat_float,
                'lng': lng_float,
                'timestamp': str(time) if time else '',
                'altitude': alt_float,
                'speed': spd_float
            })
            table_rows.append([str(time), f"{lat_float:.6f}", f"{lng_float:.6f}", f"{alt_float:.2f}", f"{spd_float:.2f}"])
            
        elif firmware_type == "PX4":
            timestamp, lat, lng, alt, vel = row
            # Convert to float for formatting, handle None and empty string values
            lat_float = safe_float(lat)
            lng_float = safe_float(lng)
            alt_float = safe_float(alt)
            vel_float = safe_float(vel)
            
            map_points.append({
                'lat': lat_float,
                'lng': lng_float,
                'timestamp': str(timestamp) if timestamp else '',
                'altitude': alt_float,
                'speed': vel_float
            })
            table_rows.append([str(timestamp), f"{lat_float:.6f}", f"{lng_float:.6f}", f"{alt_float:.2f}", f"{vel_float:.2f}"])
            
        else:  # Generic or Unknown firmware type
            timestamp, lat, lng, alt, spd = row
            # Convert to float for formatting, handle None and empty string values
            lat_float = safe_float(lat)
            lng_float = safe_float(lng)
            alt_float = safe_float(alt)
            spd_float = safe_float(spd)
            
            map_points.append({
                'lat': lat_float,
                'lng': lng_float,
                'timestamp': str(timestamp) if timestamp else '',
                'altitude': alt_float,
                'speed': spd_float
            })
            table_rows.append([str(timestamp), f"{lat_float:.6f}", f"{lng_float:.6f}", f"{alt_float:.2f}", f"{spd_float:.2f}"])
    
    # Calculate center point for map
    if map_points:
        center_lat = sum(point['lat'] for point in map_points) / len(map_points)
        center_lng = sum(point['lng'] for point in map_points) / len(map_points)
    else:
        center_lat, center_lng = 0, 0
    
    # Read template file
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'gps_report_template.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Template file not found: {template_path}. Please ensure the templates directory exists with gps_report_template.html file.")
    
    # Prepare template variables
    table_headers_html = ''.join(f'<th>{col}</th>' for col in columns)
    table_rows_html = ''
    for row in table_rows:
        row_html = ''.join(f'<td>{cell}</td>' for cell in row)
        table_rows_html += f'<tr>{row_html}</tr>'
    
    # Determine analysis type for title
    analysis_type = "Recovery & Analysis" if is_recovery_mode else "Analysis"
    
    # Set Google Maps API key
    api_key = google_maps_api_key if google_maps_api_key else "YOUR_GOOGLE_MAPS_API_KEY"
    
    template_vars = {
        'firmware_type': firmware_type,
        'total_points': len(map_points),
        'center_lat': center_lat,
        'center_lng': center_lng,
        'gps_points_json': json.dumps(map_points),
        'table_headers': table_headers_html,
        'table_rows': table_rows_html,
        'analysis_type': analysis_type,
        'google_maps_api_key': api_key
    }
    
    # Generate HTML using template with safe substitution
    html_content = template_content
    for key, value in template_vars.items():
        placeholder = f'${key}'
        html_content = html_content.replace(placeholder, str(value))
        print(f"Replacing {placeholder} with {str(value)[:50]}...")  # Debug info
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {html_path}")

if __name__ == '__main__':
    try:
        output = main()
    except Exception as e:
        print(e)
        raise
