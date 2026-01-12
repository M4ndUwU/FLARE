# FLARE

![Python](https://img.shields.io/badge/python-3.12-blue)

**Flight Log Analysis and REcovery for Open-Source Drones (Ardupilot, PX4, Betaflight)**  
This tool is designed to analyze flight log files from custom drones, including logs from **PX4-ULog**, **Ardupilot-Dataflash**, and **Betaflight-Blackbox**. Additionally, it can recover corrupted log files, saving the parsed data into a database.

---

## Table of Contents
1. [Supported Message Types](#support-types)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Sample Files](#sample-files)
5. [Dependencies](#dependencies)

---
## Support Message Types
### 1. ArduPilot (Dataflash Logs)

| Type | Description |
| :--- | :--- |
| **ADSB** | Broadcast detected vehicle information |
| **FNCE** | Currently loaded Geo Fence points |
| **AHR2** | Backup Attitude Heading Reference System data |
| **GPS** | Information received from GNSS systems |
| **AIS1** | ‘Position report’ AIS message |
| **MOTB** | Motor mixer information (motor fail flag) |
| **AIS4** | ‘Base Station Report’ AIS message |
| **OABR** | Object avoidance (Bendy Ruler) diagnostics |
| **ARSP** | Airspeed sensor data |
| **OADJ** | Object avoidance (Dijkstra) diagnostics |
| **BAT** | Battery Voltage and Temperature data |
| **BCL** | Battery cell Voltage information |
| **IMU** | Inertial Measurement Unit data |
| **OAVG** | Object avoidance path planning visgraph points |
| **CAM** | Camera shutter information |
| **ORGN** | Vehicle navigation origin |
| **CMD** | Executed mission command information |
| **POS** | Canonical vehicle position |
| **DSTL** | Deepstall Landing data |
| **RALY** | Rally point information |
| **EAHR** | External AHRS data |
| **TRIG** | Camera shutter information |
| **EV** | Specifically coded event message |
| **TRST** | Torqeedo System Stat (include Battery, motor) |

### 2. PX4 (ULog)

| Data | Description |
| :--- | :--- |
| **battery_status** | Battery status and operating time |
| **event** | Log level |
| **home_position** | Position set as the home position |
| **input_rc** | Remote controller input values |
| **position_setpoint_triplet** | Navigation waypoint triplet (previous, current, next) |
| **sensor_gps** | Latitude and longitude coordinates |
| **vehicle_global_position** | Latitude and longitude coordinates |
| **vehicle_global_position_groundtruth** | Ground truth coordinates (sim/replay) |
| **vehicle_gps_position** | Latitude and longitude coordinates from GPS |
| **vehicle_land_detected** | Status flags for landed state detection |
| **vehicle_local_position** | Local position coordinates (NED frame) |

### 3. Betaflight (Blackbox)

| Field / Frame | Description |
| :--- | :--- |
| **GPS** | Latitude, Longitude, Altitude, Ground Speed |
| **rcCommand** | Stick inputs from the radio controller (Roll, Pitch, Yaw, Throttle) |
| **vbatLatest** | Main battery voltage reading |
| **amperageLatest** | Current draw information |
| **gyroADC** | Raw Gyroscope sensor readings |
| **accSmooth** | Smoothed Accelerometer sensor readings |
| **motor** | Command values sent to ESCs/Motors |
| **flightModeFlags** | Active flight modes (e.g., Angle, Horizon, Air Mode) |
| **axis** | Rate and Angle data for Roll, Pitch, and Yaw |

---

## Installation

### Requirements
- **Python 3.12.5** is required to run this tool.

### Installation Steps
1. Clone the repository:
    ```bash
    git clone https://github.com/M4ndUwU/FLARE.git
    cd FLARE
    ```

2. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3. The tool is now ready for use.

---

## Usage

<img width="4289" height="1874" alt="Figure_12" src="https://github.com/user-attachments/assets/4237ce25-0d8a-49db-8b01-74cc53c8225d" />

This tool uses `argparse` for handling input arguments. You can provide both the corrupted log file fragment and a complete log file for comparison and recovery.

### Basic Usage:
```bash
python main.py <file.bin> -o <output_db_path>
```

### Arguments:
### Required:
- `filename`:
  - The fragment of the log file to be recovered.
  - **Example**: `file.bin`

- `-o`, `--output`:
  - Output path for the recovered data, saved as a database file.
  - **Example**: `path/to/output/`

### Optional:
- `-r`, `--recovery`:
  - Enable recovery mode.
  - If enabled, the tool will attempt to recover deleted or corrupted log records from dump data.

- `-i`, `--intact_filename`:
  - Input intact log file (optional in recovery mode).
  - If not provided, the firmware type must be specified for recovery.

- `-f`, `--firmware`:
  - Specify the firmware type of the drone: `ardupilot`, `px4`, or `betaflight`.
  - Required if no intact log file is provided for recovery.

- `-c`, `--cluster_size`:
  - Cluster size for parsing (default is `4096` bytes).

- `-v`, `--view`:
  - Generate an HTML report with interactive map visualization and open it in a web browser.
  - The report includes GPS flight path visualization and data table.
  - Requires internet connection for map tiles.

## Example Usage:

### Parse a Log File (Without Recovery Mode):
```bash
python main.py intact_file_ardupilot.bin -o ./result/
```

### Recover a Log File Using an Intact Log File:
```bash
python main.py partial_corrupt_dump_ardupilot.bin -r -i intact_file_ardupilot.bin -o ./result/
```

### Recover a Fragmented Log File (With Recovery Mode and Firmware Specified):
```bash
python main.py unallocated_data_log_betaflight.bbl -r -f betaflight -o ./result/
```

### Generate HTML Report with Map Visualization:
```bash
python main.py intact_file_ardupilot.bin -o ./result/ --view
```

### Recover and Generate HTML Report:
```bash
python main.py partial_corrupt_dump_ardupilot.bin -r -i intact_file_ardupilot.bin -o ./result/ --view
```

---
## Sample Test Data for Evaluation (Section 8)

The `sample_test` directory contains log files and scripts used for the evaluation described in **Section 8 of the paper**. This directory is structured to facilitate the generation, processing, and analysis of test flight logs for both **Ardupilot** and **PX4** firmware.

### Directory Structure
```
sample_test/
│── original/
│   ├── Ardupilot/
│   │   ├── logs/
│   │   ├── world/
│   ├── PX4/
│   │   ├── logs/
│   │   ├── world/
│   ├── flight_mission/
│── test/
│   ├── Ardupilot/
│   ├── PX4/
│── result/
│   ├── Ardupilot/
│   ├── PX4/
│── calc_records_Ardupilot.py
│── calc_records_PX4.py
│── calc_remain_records_Ardupilot.py
│── calc_remain_records_PX4.py
│── db_to_kml_Ardu.py
│── db_to_kml_PX4.py
│── analysis_false_positive.py
│── gen_test_log.py
```


### **Folder Descriptions**

- **`original/`**  
  Contains the original, unmodified log files used as the baseline for evaluation. These files serve as references for assessing recovery performance.

- **`test/`**  
  Stores the corrupted versions of the original log files. Various corruption scenarios are applied to simulate real-world data loss, including:
  - **First 50% of the Header (Header50)**
  - **Entire Header + First Part of Data (First25)**
  - **Last 25% of the File (Last25)**
  - **Fragmented + Randomly Rearranged (Frag50)**  

- **`result/`**  
  Holds the recovered log files after processing. These logs are reconstructed using FLARE, and their integrity is evaluated by comparing them with the original files.

### **Script Descriptions**

- **`gen_test_log.py`**  
  Generates test log files by applying predefined corruption models to the original log files. This script systematically alters log files to simulate different failure scenarios for evaluation.

- **`calc_remain_records_Ardupilot.py`**  
  Counts the number of **actual remaining FMT and non-FMT records** in Ardupilot log files generated by `gen_test_log.py`, based on identifiable byte patterns.

- **`calc_remain_records_PX4.py`**  
  Counts the number of **remaining identifiable records** in PX4 logs produced by `gen_test_log.py`, using extracted byte sequences for key message types like `home_position`, `vehicle_global_position`, and `vehicle_gps_position`.

- **`calc_records_Ardupilot.py`**  
  Analyzes and counts the number of recoverable records in **Ardupilot logs**. It is used to assess the effectiveness of the recovery process by comparing the number of extracted records across different corruption scenarios.

- **`calc_records_PX4.py`**  
  Performs the same functionality as `calc_records_Ardupilot.py`, but for **PX4 logs**. It evaluates recovery performance by identifying successfully restored records from corrupted PX4 logs.

- **`analysis_false_positive.py`**  
  Compares intact and corrupted **PX4** databases to detect false positives by identifying discrepancies in record counts across specific tables.

- **`db_to_kml_Ardu.py`**  
  Converts **Ardupilot** SQLite databases into **KML** files by extracting coordinates from `GPS` and `POS` tables for geospatial visualization.

- **`db_to_kml_PX4.py`**  
  Converts **PX4** SQLite databases into **KML** files by using data from the `vehicle_global_position_0` table.

### Usage

To generate test logs and evaluate recovery performance, run the following commands:

```bash
# Step 1: Generate corrupted test logs
python gen_test_log.py

# Step 2: Analyze recoverable records (based on byte sequences)
python calc_remain_records_Ardupilot.py
python calc_remain_records_PX4.py

# Step 3: Recover records

# Step 4: Analyze recovered records
python calc_records_Ardupilot.py
python calc_records_PX4.py

# Step 5: Identify inconsistencies and false positives
python analysis_false_positive.py

# Step 6: Convert recovered GPS data into KML for visualization
python db_to_kml_Ardu.py
python db_to_kml_PX4.py

```

---

## Sample Files

- The `/sample` folder contains sample input log files that can be used to test the tool.
    - **intact_file_firm.bin**: A fully intact log file, representing a clean and uncorrupted log. This file can be used to compare and verify the recovery of corrupted log files.
    - **partial_corrupt_dump_firm.bin**: A log file where the header and some portions of data have been corrupted. This file helps test the recovery functionality of the tool.
    - **unallocated_data_log_firm.bin**: A log file extracted from unallocated space, with some log data possibly overwritten by other files. It allows testing of the tool's ability to handle mixed or overwritten log data.

- The `/result` folder contains sample output files generated by the tool.

These folders help illustrate how the tool works with actual log data. Feel free to explore and use them for testing purposes.

### Log File Sources by Firmware:
- Ardupilot: [Ardupilot Log File](https://github.com/ArduPilot/pymavlink/blob/master/tests/test.BIN)
- PX4: [PX4 Log File](https://data.researchdatafinder.qut.edu.au/dataset/flight-logs-of4)
- Betaflight: A log file without GPS information.


note: Due to the conditions of blind review, it was necessary to omit certain details.
We will make the related sample data, which we have generated, publicly available once the paper is published.

---

## Dependencies

This tool uses the following libraries and codebases:

- **[PX4 pyulog](https://github.com/PX4/pyulog)**: For parsing PX4 ULog files.
- **[Ardupilot pymavlink](https://github.com/ArduPilot/pymavlink)**: For handling Ardupilot's Dataflash log files.
- **[Orangebox](https://github.com/atomgomba/orangebox)**: For working with Betaflight Blackbox log files.

Make sure to install the required dependencies by running:

```bash
pip install -r requirements.txt
```
---
