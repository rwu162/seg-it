import argparse
import shutil
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Import configuration first
try:
    from config import *
except ImportError:
    print("Error: config.py not found!")
    print("Please copy config.example.py to config.py and fill in your values.")
    sys.exit(1)

# Database connection using config
if DB_TYPE == "sqlite":
    engine = create_engine(f"sqlite:///{DB_PATH}")
elif DB_TYPE == "mssql":
    engine = create_engine(f'mssql+pyodbc://{DB_USERNAME}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server')
else:
    raise ValueError(f"Unsupported database type: {DB_TYPE}")


def connect_to_database():
    """Return the global engine - connection already defined at top"""
    return engine


def get_batch_file_paths_from_db(filenames_and_serials):
    """Query database once to get file paths for multiple filename/serial pairs
    
    Args:
        filenames_and_serials: list of tuples [(filename, serial), ...]
    
    Returns:
        dict: {filename: corrected_file_path, ...}
    """
    engine = connect_to_database()
    if not engine:
        return {}
    
    if not filenames_and_serials:
        return {}
    
    # Extract just filenames for the IN clause
    filenames = [filename for filename, serial in filenames_and_serials]
    
    try:
        with engine.connect() as conn:
            # Create placeholders for the IN clause
            placeholders = ','.join([f':filename_{i}' for i in range(len(filenames))])
            
            # Dynamic table name based on database type
            if DB_TYPE == "mssql":
                table_name = f"dbo.{DB_TABLE}"  # SQL Server with schema
            else:
                table_name = DB_TABLE  # SQLite without schema
                
            query = text(f"""
            SELECT {DB_FILENAME_COLUMN}, {DB_FILEPATH_COLUMN}, {DB_SERIAL_COLUMN}
            FROM {table_name}
            WHERE {DB_FILENAME_COLUMN} IN ({placeholders})
            """)
            
            # Create parameter dict for filenames
            params = {f'filename_{i}': filename for i, filename in enumerate(filenames)}
            
            result = conn.execute(query, params)
            rows = result.fetchall()
            
            # Build lookup dict from results
            file_paths = {}
            for row in rows:
                db_filename = row[0]
                db_file_path = row[1]
                db_serial = row[2]
                
                # Convert database path to network share path using config
                if db_file_path.startswith(DB_PATH_PREFIX):
                    # Remove database prefix and convert to network share
                    relative_path = db_file_path[len(DB_PATH_PREFIX):]
                    network_path = f"{NETWORK_SHARE_BASE}{relative_path.replace('/', '\\')}"
                    file_paths[db_filename] = network_path
                else:
                    # Fallback for other path formats
                    corrected_path = db_file_path.replace('/', '\\')
                    file_paths[db_filename] = corrected_path
            
            print(f"Found {len(file_paths)} file paths in database for {len(filenames)} requested files")
            return file_paths
                
    except SQLAlchemyError as e:
        print(f"Database query failed: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {}


def get_file_path_mock(filename, serial):
    """Mock function for testing - simulates database lookup without actual database"""
    # Simulate the file path format you showed: /el/HEL001/20250616/Night/OK/filename
    # This is just for testing when you don't have database access
    mock_path = f"/el/HEL001/20250616/Night/OK/{filename}"
    print(f"Mock database lookup - File: {filename}, Serial: {serial} -> Path: {mock_path}")
    return mock_path



# REMOTE FILE SWAP FUNCTIONALITY



def get_serials_from_main(folder_path: str) -> set:
    """Call main_naming.py as subprocess to get serial numbers"""
    try:
        # Call main_naming.py with --quiet flag to get just the serials
        result = subprocess.run([
            sys.executable, 'main_naming.py', 
            folder_path, 
            '--quiet'
        ], capture_output=True, text=True, check=True)
        
        # Parse the output - each line is a tuple (filename, serial)  
        file_serial_pairs = []
        for line in result.stdout.strip().split('\n'):
            if line.strip() and line.startswith('('):
                # Parse tuple format: ('filename.jpg', 'SERIAL12345')
                try:
                    import ast
                    filename, serial = ast.literal_eval(line.strip())
                    file_serial_pairs.append((filename, serial))
                except:
                    # Fallback parsing
                    parts = line.split("', '")
                    if len(parts) >= 2:
                        filename = parts[0].lstrip("('")
                        serial = parts[1].rstrip("')")
                        file_serial_pairs.append((filename, serial))
        
        return file_serial_pairs
    except subprocess.CalledProcessError as e:
        print(f"Error calling main_naming.py: {e}")
        print(f"stderr: {e.stderr}")
        return set()
    except Exception as e:
        print(f"Unexpected error: {e}")
        return set()


def get_files_with_serials(folder_path: str) -> dict:
    """Get JPG files and match them with database records using filename and serial"""
    files_with_serials = {}
    
    # Get filename-serial pairs from main_naming.py
    file_serial_pairs = get_serials_from_main(folder_path)
    if not file_serial_pairs:
        print(f"No file-serial pairs found in {folder_path}")
        return files_with_serials
    
    # Match against database records
    path = Path(folder_path)
    if path.exists() and path.is_dir():        
        for filename, serial in file_serial_pairs:
            file_path = path / filename
            if file_path.exists():
                # Use composite key (serial + filename) for unique identification
                composite_key = f"{serial}|{filename}"
                files_with_serials[composite_key] = {
                    'filename': filename,
                    'filepath': file_path,
                    'serial': serial
                }
                
        print(f"Found {len(files_with_serials)} files with matching serials")
    
    return files_with_serials


def move_files_to_remote_paths(source_files_with_serials: dict, dry_run=False):
    """Move files from local source folder to their database-specified remote paths"""
    if not source_files_with_serials:
        print("No files to process")
        return False
    
    # Prepare data for batch database query (extract filename and serial from composite key)
    filenames_and_serials = []
    for composite_key, file_data in source_files_with_serials.items():
        filename = file_data['filename']
        serial = file_data['serial']
        filenames_and_serials.append((filename, serial))
    
    print(f"\nQuerying database for {len(filenames_and_serials)} files...")
    
    # Single database query for all files
    db_file_paths = get_batch_file_paths_from_db(filenames_and_serials)
    
    #print(f"DEBUG - db_file_paths: {db_file_paths}")
    
    if not db_file_paths:
        print("No matching files found in database")
        return False
    
    moved_count = 0
    would_move_count = 0
    
    print(f"\nProcessing {len(db_file_paths)} files...")
    
    for row in db_file_paths.items():
        filename = row[0]
        remote_db_path = row[1]
        # Find the local file using composite key (serial + filename)
        local_file = None
        for composite_key, file_data in source_files_with_serials.items():
            if file_data['filename'] == filename:
                local_file = file_data['filepath']
                break
        
        if not local_file:
            print(f"WARNING: Local file not found for {filename}")
            continue
        
        if dry_run:
            print(f"Would move: {local_file} → {remote_db_path}")
            would_move_count += 1
            continue
            
        try:
            # Check if local file exists
            if not local_file.exists():
                print(f"WARNING: Local file not found: {local_file}")
                continue
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_db_path)
            os.makedirs(remote_dir, exist_ok=True)
            
            # Remove existing file at destination if it exists
            if os.path.exists(remote_db_path):
                os.remove(remote_db_path)
                print(f"REMOVED old file: {remote_db_path}")
            
            # Copy file from local to remote database path
            shutil.copy2(str(local_file), remote_db_path)
            print(f"COPIED: {filename}")
            print(f"  FROM: {local_file}")
            print(f"  TO:   {remote_db_path}")
            moved_count += 1
            
        except Exception as e:
            print(f"ERROR moving {filename}: {e}")
    
    if dry_run:
        print(f"\nWould move {would_move_count} files to remote database paths")
        return would_move_count > 0
    else:
        print(f"\n🎉 OPERATION COMPLETED SUCCESSFULLY!")
        print(f"MOVED {moved_count} files from local source to remote database paths")
        return moved_count > 0


def main():
    parser = argparse.ArgumentParser(
        description='Move files from local source folder to database-specified remote paths'
    )
    parser.add_argument(
        'source_folder',
        type=str,
        help='Path to the local source folder containing JPG files to move'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making any changes'
    )
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No files will be moved\n")
    
    # Get source files with their serial numbers
    print(f"Scanning local source folder: {args.source_folder}")
    source_files_with_serials = get_files_with_serials(args.source_folder)
    
    if not source_files_with_serials:
        print("No JPG files found in source folder")
        return
    
    # Move files from local source to remote database paths
    success = move_files_to_remote_paths(source_files_with_serials, args.dry_run)
    
    if success:
        print("\nDry run completed successfully" if args.dry_run else "\nOperation completed successfully")
    else:
        print("\nOperation failed or no files were moved")


if __name__ == "__main__":
    main()