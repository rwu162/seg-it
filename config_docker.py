# Configuration for Docker SQL Server test container

# Database Configuration
DB_SERVER = "localhost,1433"
DB_NAME = "master"  # Use master database initially
DB_USERNAME = "sa"  
DB_PASSWORD = "TestPassword123!"

# Database Schema
DB_DATABASE = "seg_it_test"  # We'll create this database
DB_TABLE = "dbo.el_desh"
DB_FILENAME_COLUMN = "file_name"
DB_FILEPATH_COLUMN = "file_path"
DB_SERIAL_COLUMN = "serial_nbr"

# Path Mapping Configuration
DB_PATH_PREFIX = "/EL/"
NETWORK_SHARE_BASE = "\\\\192.168.2.2\\homes\\ryan\\"