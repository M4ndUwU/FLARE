import os
import sqlite3
import re
import simplekml

def extract_from_db(db_path, output_folder):
    """Extracts Lat, Lng, and Alt data from GPS or POS tables in a DB and converts them into a KML file."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    kml = simplekml.Kml()
    tables = ["GPS", "POS"]  # List of tables to process

    for table in tables:
        try:
            cursor.execute(f"SELECT Lat, Lng, Alt FROM {table}")
            rows = cursor.fetchall()

            if rows:  # Process only if data exists
                for row in rows:
                    lat, lon, alt = row
                    if lat and lon and alt:  # Filter out None values
                        kml.newpoint(coords=[(lon, lat, alt)])
                print(f"Data added from table {table}: {db_path}")

        except sqlite3.OperationalError:
            print(f"Table not found: {db_path} -> Skipping {table}")
            continue  # If table does not exist, move to next

    # Save KML file only if data was added
    if kml.document:
        kml_filename = os.path.join(output_folder, os.path.basename(db_path).replace(".db", ".kml"))
        kml.save(kml_filename)
        print(f"KML saved: {kml_filename}")

    conn.close()

def extract_from_txt(txt_path, output_folder):
    """Finds POS lines in a TXT file, extracts Lat, Lng, and Alt values inside {}, and converts them to KML."""
    kml = simplekml.Kml()

    with open(txt_path, "r", encoding="utf-8") as file:
        for line in file:
            if "POS" in line:
                match = re.search(r"\{.*?Lat\s*:\s*([\d.-]+).*?Lng\s*:\s*([\d.-]+).*?Alt\s*:\s*([\d.-]+)", line)
                if match:
                    lat, lon, alt = map(float, match.groups())
                    kml.newpoint(coords=[(lon, lat, alt)])

    # Save KML file
    if kml.document:
        kml_filename = os.path.join(output_folder, os.path.basename(txt_path).replace(".txt", ".kml"))
        kml.save(kml_filename)
        print(f"KML saved: {kml_filename}")
    else:
        print(f"No POS data found: Skipping {txt_path}")

def process_folder(folder_path, output_folder):
    """Processes all DB and TXT files in the folder and converts them into KML files."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Function 2: Process DB files
        if filename.endswith(".db") and any(x in filename for x in ["header_section_corruption_b_", "data_section_corruption_b_","mix_a_b_c"]):
            extract_from_db(file_path, output_folder)

        # Function 3: Process TXT files
        elif filename.endswith(".txt") and any(x in filename for x in ["output_pymavlink_mavlogdump_intact_b"]):
            extract_from_txt(file_path, output_folder)

# Example usage
folder_path = "./result/Ardupilot"   # Input folder path
output_folder = "./kml"              # Output KML file path
process_folder(folder_path, output_folder)
