import argparse, os
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
        match_types = ['battery_status', 'event', 'home_position', 'input_rc', 'position_setpoint_triplet', 'sensor_gps', 'vehicle_global_position', 'vehicle_gps_position', 'vehicle_land_detected', 'vehicle_local_position']
    elif type == "Betaflight/Cleanflight-Blackbox File":
        match_types = []
    elif type == "Ardupilot-DataFlash File":
        match_types = ['FMT', 'ADSB', 'AHR2', 'AIS1', 'AIS4', 'ARSP', 'BAT', 'BCL', 'CAM', 'CMD', 'DSTL', 'EAHR', 'EV', 'FNCE', 'GPS', 'IMU', 'MOTB', 'OABR', 'OADJ', 'OAVG', 'ORGN', 'POS', 'RALY', 'TRIG', 'TRST']

    return match_types

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
    parser.add_argument('-c', '--cluster_size', type=int, default=4096, help='Cluster size for parsing (default is 4096)')

    # Validate that either intact_filename or firmware is provided
    args = parser.parse_args()


    log_file_name = args.filename
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
    return output

if __name__ == '__main__':
    try:
        output = main()
    except Exception as e:
        print(e)
        raise
