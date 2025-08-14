from pathlib import Path, PureWindowsPath
import argparse
import csv
import os
import fnmatch


def truncate_first_20(text: str) -> str:
    """Extract first 20 characters from text"""
    return text[:20]


def handle_network_path(path_str: str) -> Path:
    """Handle UNC network paths and convert them to a workable format"""
    # For UNC paths, use os.listdir to check existence instead of Path.exists()
    if path_str.startswith('\\\\') or path_str.startswith('//'):
        try:
            # Normalize the path
            normalized = os.path.normpath(path_str)
            # Test if we can access it
            os.listdir(normalized)
            # If we can list it, create a Path object that works with os methods
            return NetworkPath(normalized)
        except (OSError, PermissionError, FileNotFoundError):
            pass
    
    # For regular paths, use normal Path handling
    return Path(path_str)


class NetworkPath:
    """A Path-like class that handles UNC network paths using os methods"""
    def __init__(self, path_str):
        self.path_str = os.path.normpath(path_str)
    
    def __str__(self):
        return self.path_str
    
    def exists(self):
        try:
            os.listdir(self.path_str) if self.is_dir() else os.path.isfile(self.path_str)
            return True
        except (OSError, PermissionError, FileNotFoundError):
            return False
    
    def is_file(self):
        try:
            return os.path.isfile(self.path_str)
        except (OSError, PermissionError):
            return False
    
    def is_dir(self):
        try:
            return os.path.isdir(self.path_str)
        except (OSError, PermissionError):
            return False
    
    def glob(self, pattern):
        """Glob for network paths using os.listdir"""
        try:
            files = []
            for item in os.listdir(self.path_str):
                if fnmatch.fnmatch(item.lower(), pattern.lower()):
                    full_path = os.path.join(self.path_str, item)
                    files.append(NetworkPath(full_path))
            return files
        except (OSError, PermissionError):
            return []
    
    @property
    def name(self):
        return os.path.basename(self.path_str)
    
    @property 
    def stem(self):
        name = self.name
        return os.path.splitext(name)[0] if '.' in name else name
    
    @property
    def suffix(self):
        name = self.name
        return os.path.splitext(name)[1] if '.' in name else ''


def process_jpg_files(path: Path, quiet: bool = False) -> set:
    """Process JPG files and extract serial numbers"""
    serial_data = set()
    
    
    if path.is_file():
        # Single file
        if path.suffix.lower() in ['.jpg', '.jpeg']:
            serial = truncate_first_20(path.stem)
            serial_data.add(serial)
            if not quiet:
                print(f"Processed: {path.name} -> Serial: {serial}")
        else:
            if not quiet:
                print(f"Warning: '{path.name}' is not a JPG file")
    
    elif path.is_dir():
        # Directory of files
        jpg_files = list(path.glob('*.jpg')) + list(path.glob('*.jpeg'))
        jpg_files.extend(path.glob('*.JPG'))
        jpg_files.extend(path.glob('*.JPEG'))
        
        if not jpg_files:
            if not quiet:
                print("No JPG files found in directory")
            return serial_data
            
        if not quiet:
            print(f"Found {len(jpg_files)} JPG files to process...")
        
        for filepath in jpg_files:
            serial = truncate_first_20(filepath.stem)
            serial_data.add(serial)
            if not quiet:
                print(f"Processed: {filepath.name} -> Serial: {serial}")
    
    return serial_data


def export_to_csv(serial_data: set, csv_path: Path):
    """Export serial numbers to CSV file"""
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Serial_Number'])  # Header
        for serial in sorted(serial_data):
            writer.writerow([serial])




def main():
    parser = argparse.ArgumentParser(
        description='Extract serial numbers from JPG filenames'
    )
    parser.add_argument(
        'path',
        type=str,  # Changed from Path to str to handle UNC paths
        help='Path to JPG file or directory containing JPG files'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output, show only essential information'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        help='Export serial numbers to CSV file'
    )
    
    args = parser.parse_args()
    
    # Handle network paths
    path = handle_network_path(args.path)
    
    if not path.exists():
        if not args.quiet:
            print(f"Error: '{args.path}' not found")
        return set()
    
    # Process files (extract serials)
    serial_data = process_jpg_files(path, args.quiet)
    
    # Export to CSV if requested
    if args.csv:
        try:
            export_to_csv(serial_data, args.csv)
            if not args.quiet:
                print(f"CSV exported to: {args.csv}")
        except Exception as e:
            if not args.quiet:
                print(f"Error exporting CSV: {e}")
    
    # Summary output
    if not args.quiet:
        if serial_data:
            print(f"\nTotal unique serials: {len(serial_data)}")
        else:
            print("No JPG files were processed")
    elif not args.csv:
        # In quiet mode without CSV, print serials to stdout
        for serial in sorted(serial_data):
            print(serial)
    
    return serial_data


if __name__ == "__main__":
    serial_set = main()