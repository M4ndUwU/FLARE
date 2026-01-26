import os
import pandas as pd

def find_iframe(data, index=0):
    """Find I-frame positions in Betaflight BBL file."""
    exclude_list = [b'PID', b'H I ', b'Field I ', b'axisI[', b'loopIteration']
    
    while True:
        first_iframe_index = data.find(b'I', index)
        if first_iframe_index == -1:
            return -1
        
        surrounding_text = data[max(0, first_iframe_index-10):first_iframe_index+10]
        
        exclude_found = False
        for exclude in exclude_list:
            if exclude in surrounding_text:
                exclude_found = True
                index = first_iframe_index + 1
                break
        
        if not exclude_found:
            return first_iframe_index
    return -1

def count_i_frames(data):
    """Count I (INTRA) frames in Betaflight BBL file."""
    i_count = 0
    current_idx = 0
    
    while True:
        i_frame_idx = find_iframe(data, current_idx)
        if i_frame_idx == -1:
            break
        i_count += 1
        current_idx = i_frame_idx + 1
    
    return i_count

def extract_headers(data):
    """Extract header section from Betaflight BBL file."""
    headers = {}
    index = 0
    while index < len(data):
        h_pos = data.find(b'H ', index)
        if h_pos == -1:
            break
        
        colon_pos = data.find(b':', h_pos)
        if colon_pos == -1:
            break
        
        newline_pos = data.find(b'\n', colon_pos)
        if newline_pos == -1:
            break
        
        fieldname = data[h_pos + 2:colon_pos].strip()
        value = data[colon_pos + 1:newline_pos].strip()
        headers[fieldname] = value
        index = newline_pos + 1
    
    return headers

def find_data_section_start(data):
    """Find the start of data section by locating the first I-frame."""
    return find_iframe(data)

def count_p_frames(data):
    """Count P (INTER) frames in Betaflight BBL file."""
    p_count = 0
    
    data_start = find_data_section_start(data)
    if data_start == -1:
        headers = extract_headers(data)
        if headers:
            last_header_pos = -1
            for fieldname in headers.keys():
                pos = data.find(b'H ' + fieldname)
                if pos != -1:
                    newline_pos = data.find(b'\n', pos)
                    if newline_pos != -1:
                        last_header_pos = max(last_header_pos, newline_pos)
            if last_header_pos != -1:
                data_start = last_header_pos + 1
            else:
                data_start = 0
        else:
            data_start = 0
    
    start_pos = data_start
    while start_pos < len(data):
        p_pos = data.find(b'P', start_pos)
        if p_pos == -1:
            break
        
        is_likely_p_frame = False
        if p_pos + 4 < len(data):
            next_bytes = data[p_pos + 1:p_pos + 5]
            non_printable_count = sum(1 for b in next_bytes if b < 32 or b > 126)
            if non_printable_count >= 2:
                is_likely_p_frame = True
        
        if is_likely_p_frame:
            p_count += 1
        
        start_pos = p_pos + 1
    
    return p_count

def count_ip_frames_from_bbl(bbl_path):
    """Count I and P frames directly from Betaflight BBL file."""
    try:
        with open(bbl_path, 'rb') as f:
            data = f.read()
        
        i_count = count_i_frames(data)
        p_count = count_p_frames(data)
        total_count = i_count + p_count
        
        return i_count, p_count, total_count
    except Exception as e:
        print(f"Error processing {bbl_path}: {e}")
        return 0, 0, 0

def process_files(directory):
    """Process all .bbl and .bin files in the directory and subdirectories."""
    results = []
    
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return results
    
    for root, dirs, files in os.walk(directory):
        for filename in sorted(files):
            if not (filename.endswith('.bbl') or filename.endswith('.bin')):
                continue
            
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue
            
            i_count, p_count, total_count = count_ip_frames_from_bbl(file_path)
            
            rel_path = os.path.relpath(file_path, directory)
            
            results.append({
                "File": rel_path,
                "P Frames": p_count
            })
    
    return results

def main():
    directory_path = "./test/Betaflight/"
    
    results = process_files(directory_path)
    
    if not results:
        print("No .bbl files found to process.")
        return
    
    df = pd.DataFrame(results)
    
    frag50_files = df[df['File'].str.startswith('Frag50')]
    other_files = df[~df['File'].str.startswith('Frag50')]
    
    print("\n=== Betaflight P Frame Counts (from raw BBL files) ===")
    
    if not other_files.empty:
        print("\n--- Individual Files ---")
        print(other_files.to_string(index=False))
    
    if not frag50_files.empty:
        print("\n--- Frag50 Files (Average ± Std Dev) ---")
        frag50_mean = frag50_files['P Frames'].mean()
        frag50_std = frag50_files['P Frames'].std()
        frag50_count = len(frag50_files)
        print(f"Frag50 files: {frag50_count} files")
        print(f"Average: {frag50_mean:.2f} ± {frag50_std:.2f}")
        print(f"Range: {frag50_files['P Frames'].min()} ~ {frag50_files['P Frames'].max()}")
    
    print("\n=== Summary ===")
    print(f"Total files processed: {len(results)}")
    print(f"Total P frames: {df['P Frames'].sum()}")

if __name__ == "__main__":
    main()
