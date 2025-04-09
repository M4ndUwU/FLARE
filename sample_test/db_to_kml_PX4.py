import os
import sqlite3
import simplekml
import csv

def extract_from_db(db_path, output_folder):
    """Extracts lat, lon, and alt data from the vehicle_global_position_and_vehicle_global_position_groundtruth table and converts them into a KML file."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the table exists
    try:
        cursor.execute("SELECT lat, lon, alt FROM vehicle_global_position_and_vehicle_global_position_groundtruth")
    except sqlite3.OperationalError:
        print(f"Table not found: {db_path} -> Skip")
        conn.close()
        return  # Exit if the table does not exist

    kml = simplekml.Kml()
    for row in cursor.fetchall():
        lat, lon, alt = row
        if lat and lon and alt:  # Filter out None values
            kml.newpoint(coords=[(lon, lat, alt)])

    # Save KML file
    kml_filename = os.path.join(output_folder, os.path.basename(db_path).replace(".db", ".kml"))
    kml.save(kml_filename)
    conn.close()
    print(f"KML saved: {kml_filename}")

def extract_from_csv_and_save_kml(csv_folder, output_kml_path):
    """Extracts lat, lon, alt from matching CSV files and writes them into a single KML file."""
    kml = simplekml.Kml()

    for filename in os.listdir(csv_folder):
        if ("vehicle_global_position" in filename or "vehicle_global_position_groundtruth" in filename) and filename.endswith(".csv"):
            file_path = os.path.join(csv_folder, filename)
            with open(file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        lat = float(row.get("lat", 0))
                        lon = float(row.get("lon", 0))
                        alt = float(row.get("alt", 0))
                        if lat != 0 and lon != 0:
                            kml.newpoint(coords=[(lon, lat, alt)])
                    except (ValueError, TypeError):
                        continue  # Skip invalid rows

    if kml.document.features:
        kml.save(output_kml_path)
        print(f"KML saved from CSVs: {output_kml_path}")
    else:
        print("No valid coordinates found in CSV files.")

def process_folder(folder_path, output_folder):
    """Finds DB files with '_a_' in the name and converts them into KML files."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(folder_path):
        if "_a_" in filename and filename.endswith(".db"):
            file_path = os.path.join(folder_path, filename)
            extract_from_db(file_path, output_folder)
        if "mix_" in filename and filename.endswith(".db"):
            file_path = os.path.join(folder_path, filename)
            extract_from_db(file_path, output_folder)


    csv_folder = "./result/PX4/intact_a"
    csv_output_kml = "./kml/intacta_combined.kml"
    extract_from_csv_and_save_kml(csv_folder, csv_output_kml)

# Example usage
folder_path = "./result/PX4"     # Input folder path
output_folder = "./kml"          # Output KML file path
process_folder(folder_path, output_folder)
