import argparse
import shutil
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Import configuration
try:
    from config import *
except ImportError:
    print("Error: config.py not found!")
    print("Please copy config.example.py to config.py and fill in your values.")
    sys.exit(1)

# HARDCODED PATHS FOR TESTING - UPDATE THESE FOR YOUR ENVIRONMENT!!!
TARGET_FOLDER = r"\\192.168.2.2\home\Target\6-16-2025 OK"  # Target folder path

# Database connection will be configured via user input


def get_database_config():
    """Get database configuration from config file or user input as fallback"""
    # Try to use config values first
    if all([DB_SERVER, DB_NAME, DB_USERNAME, DB_PASSWORD]):
        return DB_SERVER, DB_NAME, DB_USERNAME, DB_PASSWORD
    
    # Fallback to user input if config is incomplete
    print("Database configuration incomplete in config.py")
    print("SQL Server Database Configuration:")
    server = input("Enter server name/IP (e.g., localhost, 192.168.1.100): ").strip()
    database = input("Enter database name: ").strip()
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    
    return server, database, username, password


def connect_to_database(server=None, database=None, username=None, password=None):
    """Connect to SQL Server database using SQLAlchemy"""
    if not all([server, database]):
        server, database, username, password = get_database_config()
    
    try:
        # Build SQLAlchemy connection string for SQL Server Authentication
        conn_str = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
        
        engine = create_engine(conn_str)
        # Test the connection
        conn = engine.connect()
        conn.close()  # Close test connection
        print("Database connection successful!")
        return engine
    except SQLAlchemyError as e:
        print(f"Database connection failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


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
            
            query = text(f"""
            SELECT {DB_FILENAME_COLUMN}, {DB_FILEPATH_COLUMN}, {DB_SERIAL_COLUMN}
            FROM [{DB_DATABASE}].[{DB_TABLE}]
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


# --------------------------------------------------------------------------------
# REMOTE FILE SWAP FUNCTIONALITY
# --------------------------------------------------------------------------------


def get_serials_from_main(folder_path: str) -> set:
    """Call main_naming.py as subprocess to get serial numbers"""
    try:
        # Call main_naming.py with --quiet flag to get just the serials
        result = subprocess.run([
            sys.executable, 'main_naming.py', 
            folder_path, 
            '--quiet'
        ], capture_output=True, text=True, check=True)
        
        # Parse the output - each line should be a serial number
        serials = set()
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                serials.add(line.strip())
        
        return serials
    except subprocess.CalledProcessError as e:
        print(f"Error calling main_naming.py: {e}")
        print(f"stderr: {e.stderr}")
        return set()
    except Exception as e:
        print(f"Unexpected error: {e}")
        return set()


def get_files_with_serials(folder_path: str) -> dict:
    """Get JPG files and match them with serials from main.py"""
    files_with_serials = {}
    
    # Get serials from main_naming.py
    serials = get_serials_from_main(folder_path)
    if not serials:
        print(f"No serials found in {folder_path}")
        return files_with_serials
    
    # Find JPG files and match them to serials
    path = Path(folder_path)
    if path.exists() and path.is_dir():
        jpg_files = list(path.glob('*.jpg')) + list(path.glob('*.jpeg'))
        jpg_files.extend(path.glob('*.JPG'))
        jpg_files.extend(path.glob('*.JPEG'))
        
        for filepath in jpg_files:
            serial = filepath.stem[:20]  # First 20 characters
            if serial in serials:
                files_with_serials[serial] = filepath
                
        print(f"Found {len(files_with_serials)} files with matching serials")
    
    return files_with_serials


def move_files_to_remote_paths(source_files_with_serials: dict, dry_run=False):
    """Move files from local source folder to their database-specified remote paths"""
    if not source_files_with_serials:
        print("No files to process")
        return False
    
    # Prepare data for batch database query
    filenames_and_serials = []
    for serial, local_filepath in source_files_with_serials.items():
        filename = local_filepath.name
        filenames_and_serials.append((filename, serial))
    
    print(f"\nQuerying database for {len(filenames_and_serials)} files...")
    
    # Single database query for all files
    db_file_paths = get_batch_file_paths_from_db(filenames_and_serials)
    
    if not db_file_paths:
        print("No matching files found in database")
        return False
    
    moved_count = 0
    would_move_count = 0
    
    print(f"\nProcessing {len(db_file_paths)} files...")
    
    for filename, remote_db_path in db_file_paths.items():
        # Find the local file
        local_file = None
        for serial, local_filepath in source_files_with_serials.items():
            if local_filepath.name == filename:
                local_file = local_filepath
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
            
            # Move file from local to remote database path
            shutil.move(str(local_file), remote_db_path)
            print(f"MOVED: {filename}")
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