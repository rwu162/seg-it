# SEG-IT

Python tool for processing EL (Electroluminescence) image files with database integration and automated file movement.

## What It Does

**main_naming.py**: Extracts serial numbers from JPG filenames
- Takes first 20 characters of filename (without .jpg extension)
- Can process single files or entire directories
- Outputs filename-serial pairs for database lookup

**remote_update.py**: Moves files to their correct network locations
- Uses main_naming.py to get serials from local JPG files
- Queries database to find where each file should go
- Moves files from local folder to database-specified network paths
- Handles path conversion from database format to network share format

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create configuration file:
   ```bash
   # Create your own config.py - contains sensitive company data
   # Edit with your database credentials and network paths
   ```

3. Setup test database:
   ```bash
   python setup_sqlite_database.py
   ```

## Configuration

**IMPORTANT**: Create your own `config.py` file as it stores sensitive company data. Never commit this file.

Key settings:
- `DB_TYPE` - "sqlite" for testing, "mssql" for production
- Database connection details (server, credentials for SQL Server)
- Path mapping: `DB_PATH_PREFIX` and `NETWORK_SHARE_BASE`

The tool converts database paths like `/EL/HEL001/file.jpg` to network paths like `\\server\share\HEL001\file.jpg`

## Usage

### Extract Serial Numbers (main_naming.py)
```bash
python main_naming.py /path/to/images           # Show serials for all JPGs
python main_naming.py /path/to/images --csv out.csv  # Export to CSV
python main_naming.py /path/to/images --quiet        # Just output tuples
```

### Move Files to Network Paths (remote_update.py)
```bash
python remote_update.py /path/to/local/files --dry-run  # Preview only
python remote_update.py /path/to/local/files            # Actually move files
```

**How it works:**
1. Scans local folder for JPG files
2. Extracts serial numbers using main_naming.py
3. Queries database to find correct network path for each file
4. Moves files from local folder to network destinations

### Test Database Connection
```bash
python test_database_connection.py
```

## Security

- Never commit `config.py` - contains sensitive credentials
- Test in development before production use
- Ensure proper network share permissions