from pathlib import Path
import argparse
import csv


def truncate_first_20(text: str) -> str:
    """Extract first 20 characters from text"""
    return text[:20]


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
        type=Path,
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
    
    if not args.path.exists():
        if not args.quiet:
            print(f"Error: '{args.path}' not found")
        return set()
    
    # Process files
    serial_data = process_jpg_files(args.path, args.quiet)
    
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