from pymavlink import mavutil
import sys, time, inflect, os
import sqlite3

# init inflect engine
p = inflect.engine()


class MsgQueryData(object):
    """docstring for MsgQueryData."""

    def __init__(self, type):
        self.type = type
        self.query = None
        self.has_query = False
        self.data = None
        self.has_data = False

    def has_query(self):
        return self.has_query
    def set_query(self, query):
        self.query = query
        self.has_query = True
    def get_query(self):
        return self.query
    def append_data(self, data):
        if not self.has_data:
            self.data = []
            self.has_data = True
        self.data.append(data)
        return
    def get_data(self):
        return self.data

class MsgQueryDataFactory:
    _instances = {}

    @classmethod
    def get_msgQueryData(cls, type):
        key = (type)

        if key not in cls._instances:
            # If the instance does not exist, create a new one.
            cls._instances[key] = MsgQueryData(type)
        return cls._instances[key]

    @classmethod
    def get_all_instances(cls):
        return list(cls._instances.values())



def number_to_words(column_name):
    # Check if the column name is a number, and if it is, convert the number to its corresponding English word.
    if column_name.isdigit():
        return p.number_to_words(column_name)
    return column_name

def save_db(m, types, output):
    conn = sqlite3.connect(output)
    cursor = conn.cursor()

    for msg in m:
        #create table based match_types and FMT
        if msg['mavpackettype'] == 'FMT' and msg['Name'] in types:
            # create sql query
            columns = msg['Columns'].split(",")
            column_definitions = ', '.join([f"'{number_to_words(col)}' TEXT" for col in columns])
            sql_query = f"CREATE TABLE IF NOT EXISTS {msg['Name']} (row_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, {column_definitions})"

            # create talbe
            try:
                cursor.execute(sql_query)
            except Exception as e:
                print(sql_query, e)
            conn.commit()

        if msg['mavpackettype'] in types:
            table_name = msg['mavpackettype']
            msgQuerySet = MsgQueryDataFactory.get_msgQueryData(table_name)

            # Exclude the key 'mavpackettype'.
            filtered_keys = [key for key in msg if key != 'mavpackettype']

            if not msgQuerySet.has_query:
                columns = ', '.join(filtered_keys)
                placeholders = ', '.join(['?'] * len(filtered_keys))
                sql_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                msgQuerySet.set_query(sql_query)

            # prepare data
            filtered_data = [str(msg[key]) for key in filtered_keys if key in msg]
            msgQuerySet.append_data(filtered_data)
        else:
            print("what", msg)


    #save
    instances = MsgQueryDataFactory.get_all_instances()
    for msgq in instances:
        try:
            cursor.executemany(msgq.get_query(), msgq.get_data())
        except Exception as e:
            print(e)
    conn.commit()
    conn.close()

def df_parser(filename, match_types, output):
    #mavlogdump.py
    mlog = mavutil.mavlink_connection(filename)

    msgs = []
    # Keep track of data from the current timestep. If the following timestep has the same data, it's stored in here as well. Output should therefore have entirely unique timesteps.
    while True:
        m = mlog.recv_match(blocking=False, type=match_types)
        if m is None:
            break

        msg = m.to_dict()

        # Grab the timestamp.
        timestamp = getattr(m, '_timestamp', 0.0)
        # Otherwise we output in a standard Python dict-style format
        s = "%s.%02u" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)), int(timestamp*100.0)%100)

        msg['timestamp'] = s

        #print(msg)
        msgs.append(msg)

    save_db(msgs, match_types, output)

def df_recover(filename, match_types, orig_log_file_name, cluster_size, output):
    # define constant
    DATAFLASH_HEADER_BYTES = b'\xA3\x95\x80\x80\x59\x46\x4D\x54'  # DataFlash Header ("A3 95 80 80 YFMT")

    def extract_fmt_messages(data):
        """
        Extract FMT messages from binary data and return them as a dictionary.
        The key will be the message name (Name), and the value will be the corresponding FMT data.
        """
        fmt_dict = {}
        fmt_start = 0
        while True:
            # Find the start pattern of the FMT message ('A3 95 80').
            fmt_start = data.find(b'\xA3\x95\x80', fmt_start)
            if fmt_start == -1:
                break
            try:
                # Check the length of the FMT message (found in the 2nd byte).
                fmt_length = 0x59

                # The message name (Name) is located from the 6th byte and spans 4 bytes.
                fmt_name = data[fmt_start + 5:fmt_start + 9].decode('ascii').strip()

                # Extract the entire FMT message data, including the Type and Length fields.
                fmt_data = data[fmt_start:fmt_start + fmt_length]
                tt = data[fmt_start + 9:fmt_start + fmt_length].decode('ascii').strip()

                # Add it to the dictionary.
                fmt_dict[fmt_name] = fmt_data
            except:
                fmt_start += 1
                continue

            # Move the position to find the next FMT message.
            fmt_start += fmt_length
        return fmt_dict

    def find_next_a3_95_non_80(data, start_idx):
        # Find the next pattern starting with 'A3 95', but where the byte following it is not '80', excluding FMT.
        idx = data.find(b'\xA3\x95', start_idx)
        while idx != -1:
            if data[idx + 2] != 0x80:
                return idx
            idx = data.find(b'\xA3\x95', idx + 1)
        return -1

    def find_all_a3_95_non_80(data):
        # Dictionary to store the position and data chunk
        result = {}
        start_idx = 0

        while True:
            current_idx = find_next_a3_95_non_80(data, start_idx)
            if current_idx == -1:
                break

            # Find the next occurrence of 'A3 95' to define the chunk end
            next_idx = data.find(b'\xA3\x95', current_idx + 3)

            # Slice the data from current_idx to next_idx or to the end of the data
            if next_idx == -1:
                result[current_idx] = data[current_idx:]
            else:
                result[current_idx] = data[current_idx:next_idx]

            # Move the starting point forward
            start_idx = next_idx if next_idx != -1 else len(data)

        return result

    def recover_missing_fmt(corrupted_data, original_data):
        """
        Copy and add the FMT messages from the valid file that are missing in the corrupted file.
        """
        recovered_fmt_data = b""

        # Extract FMT messages from both the corrupted file and the valid file.
        corrupted_fmt_dict = extract_fmt_messages(corrupted_data)
        original_fmt_dict = extract_fmt_messages(original_data)

        # Recover the FMT messages that are missing from the corrupted file.
        for fmt_name, fmt_data in original_fmt_dict.items():
            if fmt_name not in corrupted_fmt_dict:
                print(f"Recovering FMT message '{fmt_name}' from Intact Log File")
                recovered_fmt_data += fmt_data  # Add the FMT data that is missing from the corrupted file.

        for fmt_name, fmt_data in corrupted_fmt_dict.items():
            recovered_fmt_data += fmt_data  # Add the original FMT data that was already present.
        return recovered_fmt_data

    def build_recover_fmt_dict(recover_data, match_types):
        """
        Scans 'recover_data' for the pattern:
          [0xA3, 0x95, 0x80, msg_type(1 byte), length(1 byte), name(4 bytes)]
        and returns a dict: { msg_type: (length, name_str) },
        but only if name_str is in match_types.

        Total record size = 9 bytes:
          3 (header) + 1 (msg_type) + 1 (length) + 4 (name)
        """

        fmt_dict = {}
        i = 0
        data_len = len(recover_data)

        # We need at least 9 bytes per record
        while i <= data_len - 9:
            if (recover_data[i]   == 0xA3 and
                recover_data[i+1] == 0x95 and
                recover_data[i+2] == 0x80):

                msg_type = recover_data[i+3]
                length   = recover_data[i+4]
                name_bytes = recover_data[i+5 : i+9]
                name_str = name_bytes.rstrip(b'\x00').decode('ascii', errors='replace').strip()

                # Only store if name_str is in match_types
                if name_str in match_types:
                    fmt_dict[msg_type] = (length, name_str)

                i += 9  # move past this record
            else:
                i += 1

        return fmt_dict

    def find_all_len_verfied_a3_95_non_80(corrupted_data, recover_fmt_data):
        """
        Strictly verifies that the next 2 bytes after the message are 0xA3, 0x95.
        'recover_fmt_data' should be { msg_type: (length, name_str) }.
        Returns { offset: bytes_chunk } with only valid messages.
        """
        results = {}
        i = 0
        data_len = len(corrupted_data)

        while i < data_len - 2:
            # Check for A3 95
            if corrupted_data[i] == 0xA3 and corrupted_data[i + 1] == 0x95:
                msg_type = corrupted_data[i + 2]

                # Skip msg_type == 0x80 and unknown types
                if msg_type != 0x80 and msg_type in recover_fmt_data:
                    length, name_str = recover_fmt_data[msg_type]
                    end_pos = i + length  # index just after this message

                    # 1) Check if we have enough bytes for this message
                    if end_pos <= data_len:
                        # 2) Strictly check if the next 2 bytes are A3 95
                        #    We need at least end_pos + 2 bytes
                        if end_pos + 1 < data_len:
                            if (corrupted_data[end_pos]     == 0xA3 and
                                corrupted_data[end_pos + 1] == 0x95):
                                # Valid message chunk
                                chunk = corrupted_data[i : end_pos]
                                results[i] = chunk
                                i += length
                                continue

            # If any check fails, move one byte forward
            i += 1

        return results



    def merge_data_by_cluster_size(data_dict, cluster_size):
        # Sort the dictionary by index
        sorted_data = sorted(data_dict.items(), key=lambda x: x[0])

        merged_clusters = {}
        current_cluster_idx = sorted_data[0][0] // cluster_size
        merged_data = b""

        for idx, data in sorted_data:
            cluster_idx = idx // cluster_size

            if cluster_idx != current_cluster_idx:
                merged_clusters[current_cluster_idx] = merged_data
                current_cluster_idx = cluster_idx
                merged_data = b""

            merged_data += data

        # Store the final cluster
        merged_clusters[current_cluster_idx] = merged_data

        return merged_clusters

    # Save recovered_data to a file in ./tmp/ directory
    def save_recovered_data(recovered_data, file_index):
        # Create the tmp directory if it doesn't exist
        if not os.path.exists('./tmp/'):
            os.makedirs('./tmp/')

        # File name pattern
        file_path = f'./tmp/recovered_data_{file_index}.bin'

        # Save recovered data to the file
        with open(file_path, 'wb') as f:
            f.write(recovered_data)

        return file_path

    # Open the corrupted log file in binary mode.
    with open(filename, 'rb') as f:
        corrupted_data = f.read()

    # 1. Search for the pattern where 0xA3 0x95 is followed by something other than 0x80 (Data Section).
    next_non_80_pos = find_next_a3_95_non_80(corrupted_data, 0)

    if next_non_80_pos == -1:
        raise Exception("No Log Record found, recovery not needed.")
    else:
        print(f"Log Record found at position {next_non_80_pos}, recovering...")

    # 2. Search FMT (Schema Records)
    if orig_log_file_name:
        # Open the Intact Log
        with open(orig_log_file_name, 'rb') as f:
            orig_data = f.read()

        recover_fmt_data = recover_missing_fmt(corrupted_data, orig_data)
    else:
        recover_fmt_data = recover_missing_fmt(corrupted_data, b"")

    # Assuming find_all_a3_95_non_80(corrupted_data) returns a dictionary like {position: data}
    #corrupted_data_dict = find_all_a3_95_non_80(corrupted_data)
    recover_dict = build_recover_fmt_dict(recover_fmt_data,match_types)
    corrupted_data_dict = find_all_len_verfied_a3_95_non_80(corrupted_data, recover_dict)
    clustered_data = merge_data_by_cluster_size(corrupted_data_dict, cluster_size)

    # Parse
    msgs = []
    first_idx = None
    for idx, one_clustered_data in clustered_data.items():
        if first_idx == None:
            first_idx = idx
        recovered_data = recover_fmt_data + one_clustered_data
        file_name = save_recovered_data(recovered_data, idx)

        #mavlogdump.py
        mlog = mavutil.mavlink_connection(file_name)

        # Keep track of data from the current timestep. If the following timestep has the same data, it's stored in here as well. Output should therefore have entirely unique timesteps.
        while True:
            m = mlog.recv_match(blocking=False, type=match_types)
            if m is None:
                break

            msg = m.to_dict()

            if msg['mavpackettype'] == 'FMT' and first_idx != idx:
                continue

            # Grab the timestamp.
            timestamp = getattr(m, '_timestamp', 0.0)
            # Otherwise we output in a standard Python dict-style format
            s = "%s.%02u" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)), int(timestamp*100.0)%100)

            msg['timestamp'] = s

            #print(msg)
            msgs.append(msg)

    # save
    save_db(msgs, match_types, output)
