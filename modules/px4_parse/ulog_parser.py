import sqlite3
import numpy as np
import re, struct, datetime

from .core import ULog
from .px4_events import PX4Events

def get_defaults(ulog, default):
    """ get default params from ulog """
    assert ulog.has_default_parameters, "Log does not contain default parameters"

    if default == 'system': return ulog.get_default_parameters(0)
    if default == 'current_setup': return ulog.get_default_parameters(1)
    raise ValueError('invalid value \'{}\' for --default'.format(default))

def load_params(ulog, output_file):
    params = ulog.initial_parameters

    #params = get_defaults(ulog, 'system')
    #params = get_defaults(ulog, 'current_setup')

    param_keys = sorted(params.keys())


    delimiter = ','

    for param_key in param_keys:
        output_file.write(param_key)
        output_file.write(delimiter)
        output_file.write(str(params[param_key]))
        if True:
            for t, name, value in ulog.changed_parameters:
                if name == param_key:
                    output_file.write(delimiter)
                    output_file.write(str(value))
        output_file.write('\n')

def load_info(ulog):
    """Show general information from an ULog"""
    info_msgs = dict()

    if ulog.file_corruption:
        print("Warning: file has data corruption(s)")

    m1, s1 = divmod(int(ulog.start_timestamp/1e6), 60)
    h1, m1 = divmod(m1, 60)
    m2, s2 = divmod(int((ulog.last_timestamp - ulog.start_timestamp)/1e6), 60)
    h2, m2 = divmod(m2, 60)
    #print("Logging start time: {:d}:{:02d}:{:02d}, duration: {:d}:{:02d}:{:02d}".format(h1, m1, s1, h2, m2, s2))
    info_msgs['Logging start time'] = "{:d}:{:02d}:{:02d}".format(h1, m1, s1)
    info_msgs['duration'] = "{:d}:{:02d}:{:02d}".format(h2, m2, s2)

    dropout_durations = [dropout.duration for dropout in ulog.dropouts]
    if len(dropout_durations) == 0:
        #print("No Dropouts")
        info_msgs['Dropouts'] = "No"
    else:
        info_msgs["Dropouts-count"] = "{:}".format(len(dropout_durations))
        info_msgs["Dropouts-total_duration"] = "{:.1f} s".format(sum(dropout_durations)/1000.)
        info_msgs["Dropouts-max"] = "{:} ms".format(max(dropout_durations))
        info_msgs["Dropouts-mean"] = "{:} ms".format(int(sum(dropout_durations)/len(dropout_durations)))

    version = ulog.get_version_info_str()
    if not version is None:
        #print('SW Version: {}'.format(version))
        info_msgs["SW Version"] = "{}".format(version)

    #print("Info Messages:")
    for k in sorted(ulog.msg_info_dict):
        if not k.startswith('perf_'):
            #print(" {0}: {1}".format(k, ulog.msg_info_dict[k]))
            info_msgs[k] = ulog.msg_info_dict[k]

    return info_msgs

def load_msg(ulog):
    msg_msgs = []
    logged_messages = [(m.timestamp, m.log_level_str(), m.message) for m in ulog.logged_messages]

    # If this is a PX4 log, try to get the events too
    if ulog.msg_info_dict.get('sys_name', '') == 'PX4':
        px4_events = PX4Events()
        events = px4_events.get_logged_events(ulog)

        for t, log_level, message in logged_messages:
            # backwards compatibility: a string message with appended tab is output
            # in addition to an event with the same message so we can ignore those
            if message[-1] == '\t':
                continue
            events.append((t, log_level, message))

        logged_messages = sorted(events, key=lambda m: m[0])

    for t, log_level, message in logged_messages:
        m1, s1 = divmod(int(t/1e6), 60)
        h1, m1 = divmod(m1, 60)
        msg_msg = ["{:d}:{:02d}:{:02d}".format(h1, m1, s1),  "{:}".format(log_level), "{:}".format(message)]
        msg_msgs.append(msg_msg)
    return msg_msgs

def load_data(ulog, match_types):
    data_msgs = []
    data = ulog.data_list

    for d in data:
        data_msg = []
        if not d.name.replace('/', '_') in match_types:
            continue

        #print(d.name.replace('/', '_'), d.multi_id)
        data_msg.append([d.name.replace('/', '_'), d.multi_id])

        data_keys = [f.field_name for f in d.field_data]
        data_keys.remove('timestamp')
        data_keys.insert(0, 'timestamp')  # we want timestamp at first position
        data_msg.append(data_keys)

        # write the data
        for i in range(0, len(d.data['timestamp'])):
            data_body = []
            for k in range(len(data_keys)):
                data_body.append(str(d.data[data_keys[k]][i]))
            data_msg.append(data_body)
        data_msgs.append(data_msg)
    return data_msgs

def save_db(output, info_msgs, msg_msgs, data_msgs):
    conn = sqlite3.connect(output)
    cursor = conn.cursor()

    #info
    #create table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS info_messages (
        key TEXT,
        value TEXT
    )
    ''')
    # convert dict to tuple list
    if info_msgs:
        data_tuples = [(key, value) for key, value in info_msgs.items()]

        # insert data to db
        try:
            cursor.executemany('INSERT INTO info_messages (key, value) VALUES (?, ?)', data_tuples)
            conn.commit()
        except sqlite3.IntegrityError:
            print("Error: A duplicate key was found. No data has been inserted.")



    #msg
    # Create Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logged_string_message (
        timestamp TEXT,
        log_level TEXT,
        message TEXT
    )
    ''')

    # Insert data to DB
    cursor.executemany('INSERT INTO logged_string_message (timestamp, log_level, message) VALUES (?, ?, ?)', msg_msgs)
    conn.commit()

    #data
    for data_array in data_msgs:
        table_name = data_array[0][0] + "_" + str(data_array[0][1])

        columns = data_array[1]

        # Apply the transformed column names to the SQL query.
        columns_sql = ", ".join([f"'{column}' TEXT" for column in columns])
        create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql});"

        # Create table
        cursor.execute(create_table_sql)

        # prepare command for inserting data
        insert_sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{column}`' for column in columns])}) VALUES ({', '.join(['?' for _ in columns])});"


        # insert data
        try:
            cursor.executemany(insert_sql, data_array[2:])
        except Exception as e:
            print(e)
            print(insert_sql)
    conn.commit()
    conn.close()

    return

def ulog_parser(ulog_file_name, match_types, output):
    ulog = ULog(ulog_file_name, None, False)

    #B, F, I, M, O
    #https://github.com/PX4/pyulog/blob/main/pyulog/info.py
    info_msgs = load_info(ulog)
    #print(info_msgs)

    #P, Q
    #https://github.com/PX4/pyulog/blob/main/pyulog/params.py
    #load_params(ulog, output_file)

    #l
    #https://github.com/PX4/pyulog/blob/main/pyulog/messages.py
    msg_msgs = load_msg(ulog)
    #print(msg_msgs)

    #A, R, D, C, S
    #https://github.com/PX4/pyulog/blob/main/pyulog/ulog2csv.py
    data_msgs = load_data(ulog, match_types)
    #print(data_msgs)
    #[0] : Name
    #[1] : Schema
    #[2:] : data
    save_db(output, info_msgs, msg_msgs, data_msgs)

def ulog_recover(filename, orig_log_file_name, match_types, cluster_size, output):
    # Define Constant
    ULOG_HEADER_BYTES = b'\x55\x4c\x6f\x67\x01\x12\x35'

    # message types
    MSG_TYPE_FORMAT = ord('F')
    MSG_TYPE_DATA = ord('D')
    MSG_TYPE_INFO = ord('I')
    MSG_TYPE_INFO_MULTIPLE = ord('M')
    MSG_TYPE_PARAMETER = ord('P')
    MSG_TYPE_PARAMETER_DEFAULT = ord('Q')
    MSG_TYPE_ADD_LOGGED_MSG = ord('A')
    MSG_TYPE_REMOVE_LOGGED_MSG = ord('R')
    MSG_TYPE_SYNC = ord('S')
    MSG_TYPE_DROPOUT = ord('O')
    MSG_TYPE_LOGGING = ord('L')
    MSG_TYPE_LOGGING_TAGGED = ord('C')
    MSG_TYPE_FLAG_BITS = ord('B')

    Definition_Section_FULL_MSGS = [MSG_TYPE_FLAG_BITS, MSG_TYPE_FORMAT, MSG_TYPE_INFO, MSG_TYPE_INFO_MULTIPLE, MSG_TYPE_PARAMETER, MSG_TYPE_PARAMETER_DEFAULT]
    Definition_Section_MSGS = [MSG_TYPE_FORMAT]
    Data_Section_MSGS = Definition_Section_MSGS + [MSG_TYPE_DATA, MSG_TYPE_ADD_LOGGED_MSG, MSG_TYPE_REMOVE_LOGGED_MSG, MSG_TYPE_SYNC, MSG_TYPE_DROPOUT, MSG_TYPE_LOGGING, MSG_TYPE_LOGGING_TAGGED]

    type_size_map = {
        'int8_t': 1, 'uint8_t': 1,
        'int16_t': 2, 'uint16_t': 2,
        'int32_t': 4, 'uint32_t': 4,
        'int64_t': 8, 'uint64_t': 8,
        'float': 4,
        'double': 8,
        'bool': 1, 'char': 1
    }

    def find_first_data_pos(data, to_find_bytes, index=0):
        # find data and return position
        return data.find(to_find_bytes, index)

    def find_ulog_msg(data, msg):
        index = 0
        while True:
            pos = find_first_data_pos(data, msg, index)
            if pos > 2:
                msg_len = struct.unpack('<H', data[pos-2:pos])[0]
                if msg_len > 0 and data[pos+msg_len] in Data_Section_MSGS:
                    break
                else:
                    index += 1
            else:
                pos = -1
                break
        return pos

    def get_full_msg(data, pos):
        msg_len = struct.unpack('<H', data[pos-2:pos])[0]
        msg_data = data[pos-2:pos+msg_len+1]
        return msg_data

    def find_all_ulog_msg(data, msg, section):
        index = 0
        pos_arr = []
        while True:
            pos = find_first_data_pos(data, msg, index)
            if pos > 1:
                msg_len = struct.unpack('<H', data[pos-2:pos])[0]
                if msg_len > 0 and pos+msg_len+3 < len(data) and data[pos+msg_len+3] in section:
                    pos_arr.append(pos)
                    index = pos + 1
                else:
                    index += 1
            else:
                break
        return pos_arr

    def calculate_total_size(data):
        """
        A function that calculates the size of each field in a given data definition string and returns the total size.

        Parameters:
        data_str (str): strings including field and array definitions

        Returns:
        int: the total size of the fields
        """

        # Converting byte data to strings (if necessary)
        if isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = data

        # Parsing Arrays and Variables with Regular Expression
        pattern = r'(\w+)(?:\[(\d+)\])?\s+(\w+);'

        # Calculate overall size
        total_size = 0

        # Calculate the size of each field and output it
        for match in re.findall(pattern, data_str):
            data_type, array_size, field_name = match
            if "padding" in field_name:
                continue
            size = type_size_map.get(data_type, 0)  # Import the size of this data type

            if size == 0:
                print(f"Unknown type: {data_type}")
                continue

            # Resize if you have an array
            if array_size:
                size *= int(array_size)

            #print(f"Field: {field_name}, Type: {data_type}, Size: {size} bytes")
            total_size += size

        #print(f"Total size: {total_size} bytes")
        return total_size

    def split_into_clusters(logged_data_msg_pos, cluster_size):
        clusters = {}

        # Divide each location to cluster_size
        for index in logged_data_msg_pos:
            # Cluster Number Calculation
            cluster_index = index // cluster_size

            # Cluster Number Calculation
            if cluster_index not in clusters:
                clusters[cluster_index] = []

            # Add Index to Cluster
            clusters[cluster_index].append(index)

        return clusters

    # Function to recover the definition section
    def recover_define_section(corrupted_data, orig_data):
        recovered_data = b''
        corrupted_positions = find_all_ulog_msg(corrupted_data, MSG_TYPE_FORMAT, Definition_Section_FULL_MSGS)
        original_positions = find_all_ulog_msg(orig_data, MSG_TYPE_FORMAT, Definition_Section_FULL_MSGS)

        corrupted_format_msgs = dict()
        orig_format_msgs = dict()
        msg_type_dict = dict()
        msg_schema_dict = dict()

        # Create a dictionary for damaged and original messages
        for pos in corrupted_positions:
            msg_data = get_full_msg(corrupted_data, pos)
            if msg_data[3:].find(b':') == -1 or msg_data[3:].find(b';') == -1:
                continue

            msg_name = msg_data[3:msg_data.find(b':')]

            if not all(0 <= byte < 128 for byte in msg_name):
                continue

            corrupted_format_msgs[msg_name] = msg_data

        for pos in original_positions:
            msg_data = get_full_msg(orig_data, pos)
            if msg_data[3:].find(b':') == -1 or msg_data[3:].find(b';') == -1:
                continue

            msg_name = msg_data[3:msg_data.find(b':')]

            if len(msg_name) < 1 or not all(0x30 <= byte < 128 for byte in msg_name):
                continue

            orig_format_msgs[msg_name] = msg_data

        # add missing data
        for msg_name, orig_msg in orig_format_msgs.items():
            if len(msg_name) < 1 or not all(0x30 <= byte < 128 for byte in msg_name):
                continue
            if msg_name not in corrupted_format_msgs:
                recovered_data += orig_msg
                msg_type_dict[msg_name] = calculate_total_size(corrupted_msg[corrupted_msg.find(b':')+1:])
                msg_schema_dict[msg_name] = corrupted_msg[corrupted_msg.find(b':')+1:]

        # Add rest data
        # Recovered_data adds corrupted messages that are not in the source
        for msg_name, corrupted_msg in corrupted_format_msgs.items():
            if len(msg_name) < 1 or not all(0x30 <= byte < 128 for byte in msg_name):
                continue
            recovered_data += corrupted_msg
            msg_type_dict[msg_name] = calculate_total_size(corrupted_msg[corrupted_msg.find(b':')+1:])
            msg_schema_dict[msg_name] = corrupted_msg[corrupted_msg.find(b':')+1:]

        return recovered_data, msg_type_dict, msg_schema_dict

    def parse_data_chk_validity(record, schema):
        # Converting to string if schema is byte type
        if isinstance(schema, bytes):
            schema = schema.decode('utf-8')

        parsed_data = {}
        offset = 0

        # Parsing each field in the schema
        for field in schema.split(';'):
            if not field:
                continue  # Ignore empty fields

            # Ignore array type ([])
            if '[' in field and ']' in field:
                field_type, field_name = field.split('[')[0], field.split()[-1]
            else:
                field_type, field_name = field.split()

            if "padding" in field_name:
                continue

            # Check Data Type Size
            size = type_size_map.get(field_type)
            if size is None:
                raise ValueError(f"Unknown data type: {field_type}")

            # Set format to use in the Structures
            format_char = ''
            if field_type.startswith('int'):
                format_char = 'b' if '8' in field_type else ('h' if '16' in field_type else 'i')
                if '64' in field_type:
                    format_char = 'q'
            elif field_type.startswith('uint'):
                format_char = 'B' if '8' in field_type else ('H' if '16' in field_type else 'I')
                if '64' in field_type:
                    format_char = 'Q'
            elif field_type == 'float':
                format_char = 'f'
            elif field_type == 'double':
                format_char = 'd'
            elif field_type == 'bool':
                format_char = '?'
            elif field_type == 'char':
                format_char = 'c'

            # Single Value Processing
            field_data = record[offset:offset + size]
            field_value = struct.unpack(f'<{format_char}', field_data)[0]
            offset += size

            #Validation
            if field_type.startswith('int') and (field_name == 'lat' or field_name == 'lon'):
                field_value *= 0.0000001
                if (field_name == 'lat' and -90.0 <= field_value <= 90.0) or (field_name == 'lon' and -180.0 <= field_value <= 180.0):
                    # Check if the value has more than 6 decimal places
                    if abs(field_value - round(field_value, 30)) > 0:
                        return False
                else:
                    return False

            if field_name == 'lat' or field_name == 'lon':
                if (field_name == 'lat' and -90.0 <= field_value <= 90.0) or (field_name == 'lon' and -180.0 <= field_value <= 180.0):
                    # Check if the value has more than 6 decimal places
                    if abs(field_value - round(field_value, 30)) > 0:
                        return False
                else:
                    return False


            # Save extracted data
            parsed_data[field_name] = field_value

        parsed_data_values = list(parsed_data.values())
        return parsed_data_values

    def extract_field_names(schema):
        # Converting Byte Strings to Strings
        fields_section = schema.decode('utf-8')
        # separately separated from each field
        fields = fields_section.split(';')

        # Except for data types of fields except data type, "padding" is excluded
        field_names = [field.split()[-1] for field in fields if field and "padding" not in field]
        return field_names

    def find_and_parse_payload(data):
        results = []

        # Patterns to search for
        search_patterns = [f"L{i}".encode('utf-8') for i in range(8)]  # L0 ~ L7

        for pattern in search_patterns:
            index = 0
            while index < len(data):
                # Explore each pattern (L0 to L7)
                found_index = -1
                found_index = data.find(pattern, index)

                if found_index == -1:
                    # If no more patterns are found, exit
                    break

                # Extract payload length from previous 2 bytes
                if found_index >= 2:
                    payload_length = struct.unpack_from('<H', data, found_index - 2)[0]  # Little-endian 2바이트

                    if payload_length < 10:
                        index = found_index + 1
                        continue

                    # Extract payload (as long as the length of the payload behind the pattern)
                    payload_start = found_index + 1
                    payload_end = payload_start + payload_length

                    if payload_end <= len(data):
                        payload = data[payload_start:payload_end]
                        results.append({
                            'pattern': pattern.decode('utf-8'),
                            'index': found_index,
                            'payload_length': payload_length,
                            'payload': payload
                        })

                # Move to the next navigation location
                index = found_index + 1
        return results

    # Function to determine if ASCII printable range
    def is_printable(data):
        return all(32 <= byte <= 126 for byte in data)

    # Function parsing payloads
    def parse_payload(payload):
        # Function to convert log level to string
        def log_level_str(log_level):
            return {
                ord('0'): 'EMERGENCY',
                ord('1'): 'ALERT',
                ord('2'): 'CRITICAL',
                ord('3'): 'ERROR',
                ord('4'): 'WARNING',
                ord('5'): 'NOTICE',
                ord('6'): 'INFO',
                ord('7'): 'DEBUG'
            }.get(log_level, 'UNKNOWN')

        # Function that converts microseconds to hour:minute:seconds
        def microseconds_to_time(microseconds):
            # Converting microseconds to seconds
            seconds = microseconds / 1_000_000

            # convert time using darts:ta.ta
            time_format = str(datetime.timedelta(seconds=seconds))

            return time_format

        # log level (payload[1])
        log_level = payload[0]
        log_level_str_value = log_level_str(log_level)

        # Timestamp (Little Endian 8 bytes, payload[2:10])
        timestamp_microseconds = struct.unpack_from('<Q', payload, 1)[0]

        # Verifying that subsequent values are in the ASCII printable range
        message = payload[9:]
        if is_printable(message):
            message_str = message.decode('ascii')
        else:
            return False

        # result
        return [
            microseconds_to_time(timestamp_microseconds),
            log_level_str_value,
            message_str
        ]

    def key_starts_with_valid_type(key):
        """Function to determine if the key starts with the data type defined in type_size_map"""
        return any(key.startswith(data_type) for data_type in type_size_map.keys())


    def find_info_and_parse_payload(data):
        index = 0
        result_dict = {}

        while index < len(data):
            # Find the 'I' pattern
            i_index = data.find(b'I', index)
            if i_index == -1:
                break  # end if no more 'I' can be found

            # Extract message size from previous 2 bytes
            if i_index < 2:
                break  # end if no valid message exists

            msg_size = struct.unpack_from('<H', data, i_index - 2)[0]

            # extract key len
            key_len = data[i_index + 1]

            if key_len < 6:
                index = i_index + 1
                continue

            # extrafct key
            key_start = i_index + 2
            key_end = key_start + key_len
            key = data[key_start:key_end]

            # check key printable
            if not is_printable(key) or not key_starts_with_valid_type(key.decode('utf-8')):
                index = i_index + 1
                continue

            # extract value
            value_start = key_end
            value_end = value_start + (msg_size - key_len - 1)
            value = data[value_start:value_end]

            result_dict[key] = value

            index = i_index + msg_size

        return result_dict

    def sort_each_by_timestamp(data_msgs):
        # Sort internal data in each array by timestamp(x[0])
        for msg in data_msgs:
            # 3rd item to end is an array of data
            msg[2:] = sorted(msg[2:], key=lambda x: x[0])
        return data_msgs

    # Open the corrupted log file in binary mode.
    with open(filename, 'rb') as f:
        corrupted_data = f.read()

    # Open a valid log file.
    if orig_log_file_name:
        with open(orig_log_file_name, 'rb') as f:
            orig_data = f.read()
        recover_define_section_data, msg_type_dict, msg_schema_dict = recover_define_section(corrupted_data, orig_data)
    else:
        recover_define_section_data, msg_type_dict, msg_schema_dict = recover_define_section(corrupted_data, b'')
    # search and parse Logged Data
    possible_to_recover = ['home_position', 'vehicle_global_position', 'vehicle_gps_position']
    filtered_dict = {msg_name: size for msg_name, size in msg_type_dict.items() if msg_name.decode('utf-8') in possible_to_recover}
    msg_size_values = list(set(msg_type_dict.values()))

    schema_filtered_dict = {msg_name: schema_data for msg_name, schema_data in msg_schema_dict.items() if msg_name.decode('utf-8') in possible_to_recover}

    # for home_position, sensor_gps, vehicle_global_position, vehicle_gps_position
    data_msgs = []
    data_msgs = []
    logged_data_msg_pos = find_all_ulog_msg(corrupted_data, MSG_TYPE_DATA, Data_Section_MSGS)

    for msg_format_name, schema in schema_filtered_dict.items():
        data_msgs.append([[msg_format_name.decode('utf-8'),0], extract_field_names(schema)])

    if logged_data_msg_pos:
        clusters = split_into_clusters(logged_data_msg_pos, cluster_size)

        for cluster in list(clusters.values()):
            for data_pos in cluster:
                record = get_full_msg(corrupted_data, data_pos)
                # Extract id using struct with little-endian format
                id_value = struct.unpack('<H', record[3:5])[0]
                msg_size = struct.unpack('<H', record[0:2])[0]

                if not msg_size-2 in msg_size_values:
                    continue

                for msg_format_name, msg_format_size in filtered_dict.items():
                    if msg_size-2 == msg_format_size:
                        record_data = parse_data_chk_validity(record[5:], schema_filtered_dict[msg_format_name])
                        if record_data:
                            for i in range(len(data_msgs)):
                                if data_msgs[i][0][0] == msg_format_name.decode('utf-8'):
                                    data_msgs[i].append(record_data)

        data_msgs = sort_each_by_timestamp(data_msgs)

    else:
        raise Exception("No corruption found, recovery not needed.")

    msg_msgs = []
    logstr_msg = find_and_parse_payload(corrupted_data)
    if logstr_msg:
        for data in logstr_msg:
            parsed_data = parse_payload(data['payload'])
            if parsed_data:
                msg_msgs.append(parsed_data)
    msg_msgs = sorted(msg_msgs, key=lambda x: x[1])

    info_msgs = find_info_and_parse_payload(corrupted_data)

    save_db(output, info_msgs, msg_msgs, data_msgs)
