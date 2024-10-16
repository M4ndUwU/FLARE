#!/usr/bin/env python3
import sqlite3, re, os
from .orangebox import Parser

def bbl_parser(log_file_name: str, output: str):
    # Load a file
    parser = Parser.load(log_file_name)
    # or optionally select a log by index (1 is the default)
    # parser = Parser.load("btfl_all.bbl", 1)

    # create connection
    conn = sqlite3.connect(output)
    cursor = conn.cursor()

    # create headers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS headers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT,
        value TEXT
    )
    ''')

    # create events table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT
    )
    ''')

    # insert data of headers
    headers_data = [(key, str(value) if isinstance(value, list) else value) for key, value in parser.headers.items()]
    cursor.executemany('INSERT INTO headers (key, value) VALUES (?, ?)', headers_data)

    # insert data of events
    cursor.executemany('INSERT INTO events (event) VALUES (?)', parser.events)

    conn.commit()

    for i in range(1, parser.reader.log_count + 1):
        parser.set_log_index(i)

        first_seconds = None
        last_seconds = None
        frames_data = []

        # tracking first and last frame and save it
        for frame in parser.frames():
            if first_seconds is None:
                first_seconds = frame.data[1] * 1e-6
            last_seconds = frame.data[1] * 1e-6
            frames_data.append(frame.data)

        # convert sec to min:sec
        first_minutes, first_secs = divmod(first_seconds, 60)
        last_minutes, last_secs = divmod(last_seconds, 60)

        first_time_str = f"{int(first_minutes):02}:{int(first_secs):02}"
        last_time_str = f"{int(last_minutes):02}:{int(last_secs):02}"

        #create table name
        table_name = f"LOG_#{i:02}_{first_time_str}_{last_time_str}"

        # create table
        field_definitions = ", ".join([f"`{field}` TEXT" for field in parser.field_names])
        create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({field_definitions})"
        cursor.execute(create_table_query)

        # insert data
        insert_query = f"INSERT INTO `{table_name}` ({', '.join([f'`{field}`' for field in parser.field_names])}) VALUES ({', '.join(['?' for _ in parser.field_names])})"

        cursor.executemany(insert_query, frames_data)

        # commit
        conn.commit()

    # close
    conn.close()

def bbl_recover(filename, orig_log_file_name, cluster_size, output):
    BBL_HEADER_BYTES = b'\x48\x20\x50\x72\x6f\x64\x75\x63\x74\x3a\x42\x6c\x61\x63\x6b\x62\x6f\x78\x20\x66\x6c\x69\x67\x68\x74\x20\x64\x61\x74\x61\x20\x72\x65\x63\x6f\x72\x64\x65\x72\x20\x62\x79\x20\x4e\x69\x63\x68\x6f\x6c\x61\x73\x20\x53\x68\x65\x72\x6c\x6f\x63\x6b\x0a'
    BBL_FOOTER_BYTES = b'\x45\xFF\x45\x6E\x64\x20\x6F\x66\x20\x6C\x6F\x67\x00'

    def extract_log_sections_with_indexes(corrupted_data):
        extracted_logs = []
        index_pairs = []
        header_idx = 0

        while True:
            header_idx = corrupted_data.find(BBL_HEADER_BYTES, header_idx)
            if header_idx == -1:
                break

            next_header_idx = corrupted_data.find(BBL_HEADER_BYTES, header_idx + len(BBL_HEADER_BYTES))
            footer_idx = corrupted_data.find(BBL_FOOTER_BYTES, header_idx)

            # Ensure the next header appears after the current footer
            if footer_idx != -1 and (next_header_idx == -1 or footer_idx < next_header_idx):
                log_section = corrupted_data[header_idx:footer_idx + len(BBL_FOOTER_BYTES)]
                extracted_logs.append(log_section)
                index_pairs.append((header_idx, footer_idx + len(BBL_FOOTER_BYTES)))
                header_idx = footer_idx + len(BBL_FOOTER_BYTES)
            else:
                # If the next header is before the footer, move to the next header
                header_idx = next_header_idx if next_header_idx != -1 else len(corrupted_data)

        return extracted_logs, index_pairs

    def find_iframe(data, index = 0):
        # List of strings to exclude
        exclude_list = [b'PID', b'H I ', b'Field I ', b'axisI[', b'loopIteration']

        while True:
            # find first 'I'
            first_iframe_index = data.find(b'I', index)
            if first_iframe_index == -1:
                # if no more 'I'
                return -1

            #  Extract a substring around 'I' within a specified range (10 bytes before and after, adjustable if necessary)
            surrounding_text = data[max(0, first_iframe_index-10):first_iframe_index+10]

            # Check if it matches any string in the exclusion list
            exclude_found = False
            for exclude in exclude_list:
                if exclude in surrounding_text:
                    exclude_found = True
                    index = first_iframe_index + 1  # move search position to next 검색 위치를 다음으로 이동
                    break

            # Return the position of the first 'I-frame' if no excluded string is found
            if not exclude_found:
                return first_iframe_index
        return -1

    def extract_headers(data):
        """
        Extract byte data in the format "H fieldname:value\n" from the given data and return it as a dictionary.
        """
        headers = {}
        index = 0
        while index < len(data):
            # Find 'H ' (Hex value of H is 0x48, and space is 0x20)
            h_pos = data.find(b'H ', index)
            if h_pos == -1:
                break

            # Find ':'
            colon_pos = data.find(b':', h_pos)
            if colon_pos == -1:
                break

            # Find '\n'
            newline_pos = data.find(b'\n', colon_pos)
            if newline_pos == -1:
                break

            # Extract field name and value
            fieldname = data[h_pos + 2:colon_pos].strip()
            value = data[colon_pos + 1:newline_pos].strip()

            # save to dictionary
            headers[fieldname] = value

            # index update
            index = newline_pos + 1

        return headers

    # Function to determine if ASCII printable range
    def is_printable(data):
        return all(32 <= byte <= 126 for byte in data)

    def recover_missing_header(corrupted_data, orig_data):
        # Extract the header as hex values from corrupted_data and orig_data
        corrupted_headers = extract_headers(corrupted_data)
        orig_headers = extract_headers(orig_data)

        # Byte string to store the recovered data
        recovered_data = b''
        # Add headers from orig_data that are not present in corrupted_data.
        for fieldname, value in orig_headers.items():
            if fieldname not in corrupted_headers:
                # add new header
                if not is_printable(fieldname):
                    continue
                new_header = b"H " + fieldname + b":" + value + b"\n"
                #print(new_header)
                recovered_data += new_header

        # Also add headers that are present in corrupted_data.
        for fieldname, value in corrupted_headers.items():
            if not is_printable(fieldname):
                continue
            existing_header = b"H " + fieldname + b":" + value + b"\n"
            recovered_data += existing_header

        return recovered_data

    def process_i_frames_directly(corrupted_data, index_pairs):
        # Helper function to check if a range is within any index_pair
        def is_within_index_pairs(index, index_pairs):
            for start, end in index_pairs:
                if start <= index <= end:
                    return True
            return False

        i_frame_data_dict = {}

        # Start processing the corrupted data
        current_idx = 0
        while current_idx < len(corrupted_data):
            i_frame_idx = find_iframe(corrupted_data, current_idx)
            if i_frame_idx == -1:
                break  # No more I-frames

            # Check if the current I-frame index is within index_pairs
            if is_within_index_pairs(i_frame_idx, index_pairs):
                current_idx = i_frame_idx + 1  # Skip this frame if within index_pairs
                continue

            # Find the next I-frame
            next_i_frame_idx = find_iframe(corrupted_data, i_frame_idx + 1)
            if next_i_frame_idx == -1:
                next_i_frame_idx = len(corrupted_data)

            # Extract data from this I-frame to the next I-frame
            frame_data = corrupted_data[i_frame_idx:next_i_frame_idx]
            i_frame_data_dict[i_frame_idx] = frame_data

            # Move to the next frame
            current_idx = next_i_frame_idx

        return i_frame_data_dict

    def merge_i_frames_by_cluster(i_frame_dict, cluster_size):
        merged_clusters = {}

        # Go through i_frame_dict and group the data based on cluster_size
        for index, frame_data in sorted(i_frame_dict.items()):
            # Determine which cluster the index belongs to by dividing the index by the cluster size
            cluster_index = index // cluster_size

            # Initialize the cluster if it doesn't exist
            if cluster_index not in merged_clusters:
                merged_clusters[cluster_index] = b''

            # Add the frame data to the correct cluster
            merged_clusters[cluster_index] += frame_data

        return merged_clusters

    def save_to_tmp(final_data, file_name="merged_data.bin"):
        # Check if ./tmp/ directory exists, if not, create it
        tmp_dir = './tmp/'
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        # Path for the final file
        file_path = os.path.join(tmp_dir, file_name)

        # Save final_data to the file in binary write mode
        with open(file_path, 'wb') as file:
            file.write(final_data)

        return file_path

    # Open the corrupted log file in binary mode.
    with open(filename, 'rb') as f:
        corrupted_data = f.read()

    # "Identification and Extraction of Valid Log Sections"
    extracted_logs, index_pairs = extract_log_sections_with_indexes(corrupted_data)

    # Process Header
    if extracted_logs:
        recover_header_data = recover_missing_header(b'', extracted_logs[0])
    else:
        if orig_log_file_name:
            # open the completed log file
            with open(orig_log_file_name, 'rb') as f:
                orig_data = f.read()
            first_iframe_pos_orig_data = find_iframe(orig_data)
            recover_header_data = recover_missing_header(b'', orig_data[:first_iframe_pos_orig_data])

        else:
            recover_header_data = recover_missing_header(b'', corrupted_data)
            if recover_header_data[:len(BBL_HEADER_BYTES)] != BBL_HEADER_BYTES:
                recover_header_data = BBL_HEADER_BYTES + recover_header_data

    i_frame_dict = process_i_frames_directly(corrupted_data, index_pairs)
    merged_data = merge_i_frames_by_cluster(i_frame_dict, cluster_size)
    final_data = extracted_logs + [recover_header_data + value + BBL_FOOTER_BYTES for value in merged_data.values()]

    # create connection
    conn = sqlite3.connect(output)
    cursor = conn.cursor()
    for i in range(len(final_data)):
        try:
            file_path = save_to_tmp(final_data[i])
            # Load a file
            parser = Parser.load(file_path)

            if i == 0:
                # create headers table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS headers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT,
                    value TEXT
                )
                ''')

                # insert data of headers
                headers_data = [(key, str(value) if isinstance(value, list) else value) for key, value in parser.headers.items()]
                cursor.executemany('INSERT INTO headers (key, value) VALUES (?, ?)', headers_data)

            # create events table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT
            )
            ''')
            # insert data of events
            cursor.executemany('INSERT INTO events (event) VALUES (?)', parser.events)

            conn.commit()

            first_seconds = None
            last_seconds = None
            frames_data = []

            # tracking first and last frame and save it
            for frame in parser.frames():
                if first_seconds is None:
                    first_seconds = frame.data[1] * 1e-6
                last_seconds = frame.data[1] * 1e-6
                frames_data.append(frame.data)

            # convert sec to min:sec
            first_minutes, first_secs = divmod(first_seconds, 60)
            last_minutes, last_secs = divmod(last_seconds, 60)

            first_time_str = f"{int(first_minutes):02}:{int(first_secs):02}"
            last_time_str = f"{int(last_minutes):02}:{int(last_secs):02}"

            #create table name
            table_name = f"LOG_#{i:02}_{first_time_str}_{last_time_str}"

            # create table
            field_definitions = ", ".join([f"`{field}` TEXT" for field in parser.field_names])
            create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({field_definitions})"
            cursor.execute(create_table_query)

            # insert data
            insert_query = f"INSERT INTO `{table_name}` ({', '.join([f'`{field}`' for field in parser.field_names])}) VALUES ({', '.join(['?' for _ in parser.field_names])})"

            cursor.executemany(insert_query, frames_data)
        except Exception as e:
            print(e)
            continue
        # commit
        conn.commit()

    # close
    conn.close()

if __name__ == "__main__":
    import argparse, os
    from datetime import datetime
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("filename", help="Path to a .BFL file")
    parser.add_argument("output", help="output path")

    args = parser.parse_args()
    log_file_name = args.filename

    # Remove the path and extension from the filename.
    base_filename = os.path.splitext(os.path.basename(args.filename))[0]
    # Add the current timestamp.
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    new_filename = f"{base_filename}_{timestamp}.db"
    # Combine the output path with the new filename.
    output = os.path.join(args.output, new_filename)

    bbl_parser(log_file_name, output)
