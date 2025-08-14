import argparse
import shutil
import os
import subprocess
import sys
from pathlib import Path

# HARDCODED PATHS FOR TESTING - UPDATE THESE FOR YOUR ENVIRONMENT!!!
TARGET_FOLDER = r"\\192.168.2.2\home\Target\6-16-2025 OK"  # Target folder path


def get_serials_from_main(folder_path: str) -> set:
    """Call main.py as subprocess to get serial numbers"""
    try:
        # Call main.py with --quiet flag to get just the serials
        result = subprocess.run([
            sys.executable, 'main.py', 
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
        print(f"Error calling main.py: {e}")
        print(f"stderr: {e.stderr}")
        return set()
    except Exception as e:
        print(f"Unexpected error: {e}")
        return set()


def get_files_with_serials(folder_path: str) -> dict:
    """Get JPG files and match them with serials from main.py"""
    files_with_serials = {}
    
    # Get serials from main.py
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


def update_remote_files(local_files_with_serials: dict, remote_folder_path: str, dry_run=False):
    """Update files in remote folder that match local file serials"""
    if not remote_folder_path:
        print("No remote folder path specified")
        return False
    
    # Get remote files using main.py
    print(f"\nScanning remote folder: {remote_folder_path}")
    remote_files_with_serials = get_files_with_serials(remote_folder_path)
    
    if not remote_files_with_serials:
        print("No files found in remote folder to update")
        return False
    
    updated_count = 0
    would_update_count = 0
    
    print(f"\nComparing {len(local_files_with_serials)} local files with {len(remote_files_with_serials)} remote files...")
    
    for serial in local_files_with_serials:
        if serial not in remote_files_with_serials:
            print(f"No matching remote file found for serial: {serial}")
            continue
            
        local_file = local_files_with_serials[serial]
        remote_file = remote_files_with_serials[serial]
        
        if dry_run:
            print(f"Would update: {remote_file} with {local_file}")
            would_update_count += 1
            continue
            
        try:
            shutil.move(str(local_file), str(remote_file))
            print(f"MOVED: {local_file.name} → {remote_file.name}")
            updated_count += 1
        except Exception as e:
            print(f"ERROR moving {local_file.name}: {e}")
    
    if dry_run:
        print(f"\nWould update {would_update_count} files in remote folder")
        return would_update_count > 0
    else:
        print(f"\n🎉 OPERATION COMPLETED SUCCESSFULLY!")
        print(f"MOVED {updated_count} files from source to target")
        print(f"Source files have been deleted (moved to target)")
        print(f"All operations confirmed successful")
        return updated_count > 0


def main():
    parser = argparse.ArgumentParser(
        description='Update hardcoded target folder with source folder files based on matching serial numbers'
    )
    parser.add_argument(
        'source_folder',
        type=str,
        help='Path to the source folder containing JPG files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making any changes'
    )
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No files will be updated\n")
    
    # Get source files with their serial numbers using main.py
    print(f"Processing source folder: {args.source_folder}")
    source_files_with_serials = get_files_with_serials(args.source_folder)
    
    if not source_files_with_serials:
        print("No JPG files found in source folder")
        return
    
    # Update target files using hardcoded target folder
    print(f"Updating target folder: {TARGET_FOLDER}")
    success = update_remote_files(source_files_with_serials, TARGET_FOLDER, args.dry_run)
    
    if success:
        print("\nDry run completed successfully" if args.dry_run else "\nOperation completed successfully")
    else:
        print("\nOperation failed or no files were updated")


if __name__ == "__main__":
    main()