import os
import sqlite3
import simplekml

def extract_from_db(db_path, output_folder):
    """Extracts lat, lon, and alt data from the vehicle_global_position_0 table and converts them into a KML file."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the table exists
    try:
        cursor.execute("SELECT lat, lon, alt FROM vehicle_global_position_0")
    except sqlite3.OperationalError:
        print(f"Table not found: {db_path} -> Skipping vehicle_global_position")
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

def process_folder(folder_path, output_folder):
    """Finds DB files with '_a_' in the name and converts them into KML files."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(folder_path):
        if "_a_" in filename and filename.endswith(".db"):
            file_path = os.path.join(folder_path, filename)
            extract_from_db(file_path, output_folder)

# Example usage
folder_path = "./result/PX4"     # Input folder path
output_folder = "./kml"          # Output KML file path
process_folder(folder_path, output_folder)
