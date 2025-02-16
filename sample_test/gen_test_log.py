import os
import shutil
import random
import struct

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def copy_intact(src, dest_dir):
    dest_path = os.path.join(dest_dir, f"intact_{os.path.basename(src)}")
    shutil.copy2(src, dest_path)
    return dest_path

def corrupt_header_section(src, dest_dir):
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

    def find_ulog_msg(data, msg, Data_Section_MSGS):
        index = 0
        while True:
            pos = data.find(msg, index)
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

    def find_last_printable_header(data):
        """
        Finds the last position in the data where the fieldname is entirely printable.
        """
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

        def is_printable(data):
            # Function to determine if ASCII printable range
            return all(32 <= byte <= 126 for byte in data)

        headers = extract_headers(data)
        last_position = -1

        for fieldname in headers.keys():
            if is_printable(fieldname):
                # Find the last occurrence of the printable fieldname in the data
                position = data.find(b'H ' + fieldname.encode())
                if position != -1:
                    last_position = max(last_position, position)
                    last_position = data.find(b'\n', last_position)
        return last_position

    def find_next_a3_95_non_80(data, start_idx):
        # Find the next pattern starting with 'A3 95', but where the byte following it is not '80', excluding FMT.
        idx = data.find(b'\xA3\x95', start_idx)
        while idx != -1:
            if data[idx + 2] != 0x80:
                return idx
            idx = data.find(b'\xA3\x95', idx + 1)
        return -1

    type = detect_type_read_file_header(src)

    with open(src, 'rb') as f:
        data = f.read()

    if type == "PX4-ULog File":
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

        start_data_seciton = find_ulog_msg(data, MSG_TYPE_ADD_LOGGED_MSG, Data_Section_MSGS)
    elif type == "Betaflight/Cleanflight-Blackbox File":
        start_data_seciton = find_last_printable_header(data)
    elif type == "Ardupilot-DataFlash File":
        start_data_seciton = find_next_a3_95_non_80(data, 0)


    corruption_point = start_data_seciton // 2  # remove 50% of Header(definition) Section
    corrupted_data = data[corruption_point:]
    dest_path = os.path.join(dest_dir, f"header_section_corruption_{os.path.basename(src).split('.')[0]}.bin")
    with open(dest_path, 'wb') as f:
        f.write(corrupted_data)
    return dest_path

def corrupt_data_section(src, dest_dir):
    with open(src, 'rb') as f:
        data = f.read()
    corruption_point = len(data) // 4  # Remove 25%
    corrupted_data = data[corruption_point:]
    dest_path = os.path.join(dest_dir, f"data_section_corruption_{os.path.basename(src).split('.')[0]}.bin")
    with open(dest_path, 'wb') as f:
        f.write(corrupted_data)
    return dest_path

def corrupt_footer_section(src, dest_dir):
    with open(src, 'rb') as f:
        data = f.read()
    corruption_point = len(data) * 3 // 4  # Remove Last 25%
    corrupted_data = data[:corruption_point]
    dest_path = os.path.join(dest_dir, f"footer_corruption_{os.path.basename(src).split('.')[0]}.bin")
    with open(dest_path, 'wb') as f:
        f.write(corrupted_data)
    return dest_path

def create_mixed_log(log_files, dest_dir):
    chunks = []
    for log_file in log_files:
        with open(log_file, 'rb') as f:
            data = f.read()
            chunk_size = 8192  # 8KB
            chunks.extend([data[i:i+chunk_size] for i in range(0, len(data), chunk_size)])

    random.shuffle(chunks)  # Random Mix
    mixed_chunks = chunks[:len(chunks) // 2]  # Select half chunks
    mixed_data = b''.join(mixed_chunks)

    firmware_name = os.path.basename(os.path.dirname(log_files[0]))
    mixed_filename = f"mix_{'_'.join([os.path.basename(f).split('.')[0] for f in log_files])}.bin"
    dest_path = os.path.join(dest_dir, mixed_filename)
    with open(dest_path, 'wb') as f:
        f.write(mixed_data)
    return dest_path

def process_firmware_logs(original_root):
    for firmware in os.listdir(original_root):
        logs_dir = os.path.join(original_root, firmware, "logs")

        if os.path.isdir(logs_dir) and os.listdir(logs_dir):
            test_dir = os.path.join("./test", firmware)
            ensure_dir(test_dir)

            log_files = [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if os.path.isfile(os.path.join(logs_dir, f))]

            for log_file in log_files:
                copy_intact(log_file, test_dir)
                corrupt_header_section(log_file, test_dir)
                corrupt_data_section(log_file, test_dir)
                corrupt_footer_section(log_file, test_dir)

            if log_files:
                create_mixed_log(log_files, test_dir)

if __name__ == "__main__":
    process_firmware_logs("./original")
