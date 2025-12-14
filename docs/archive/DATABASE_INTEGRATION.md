# Database Integration Guide

**Copyright (c) 2025 JobDocs Contributors**
**Licensed under the MIT License - see LICENSE file for details**

This document explains how to enable and use the experimental database integration features in JobDocs.

> **⚠️ EXPERIMENTAL FEATURE**: This is placeholder code for testing and development. Do not use in production without implementing proper security measures and database connection logic. See TODO_DATABASE_INTEGRATION.md for implementation tasks.

## Overview

The database integration feature allows JobDocs to:
- Connect to JobBOSS, ERP systems, or custom SQL databases
- Pull job data automatically when new jobs are created
- Generate reports from job data
- Export reports to CSV

## Enabling Experimental Features

1. Open JobDocs
2. Go to **File > Settings**
3. Expand **Advanced Settings**
4. Check **"Enable experimental features (Database integration, Reporting)"**
5. Click **Save**
6. **Restart JobDocs** for the changes to take effect

Once enabled, you'll see:
- A new **"Reports (Beta)"** tab
- **"Experimental: Database Settings"** section in Settings

## Configuring Database Connection

### Step 1: Configure Database Settings

1. Go to **File > Settings**
2. Expand **Experimental: Database Settings**
3. Fill in your database connection details:
   - **Database Type**: Choose mssql, mysql, postgresql, or sqlite
   - **Host**: Database server address (e.g., `localhost` or `192.168.1.100`)
   - **Port**: Database port (default: 1433 for MSSQL, 3306 for MySQL, 5432 for PostgreSQL)
   - **Database**: Name of your database (e.g., `JobBOSS`)
   - **Username**: Database username
   - **Password**: Database password (stored in settings.json - see security note below)

4. Click **Test Connection** to verify settings
5. Click **Save**

### Step 2: Install Required Database Driver

Depending on your database type, install the appropriate Python driver:

```bash
# For Microsoft SQL Server (JobBOSS typically uses this)
pip install pyodbc
# Also requires ODBC Driver installation on Windows - see Troubleshooting section

# For MySQL
pip install pymysql

# For PostgreSQL
pip install psycopg2-binary

# For SQLite (built into Python, no installation needed)
```

> **Note**: These drivers are NOT included in JobDocs by default. The database integration feature will not work until you install the appropriate driver for your database type.

## Using the Reports Tab

Once experimental features are enabled and database is configured:

1. Go to the **Reports (Beta)** tab
2. Click **Connect to Database**
3. Select a report type:
   - **Job Statistics**: Overview of job counts and metrics
   - **Jobs by Customer**: Filter jobs by customer name
   - **Jobs by Date Range**: Filter jobs by creation date
   - **Recent Jobs**: Most recently created jobs
   - **Top Customers**: Customers with most jobs

4. Set filters (customer, date range) as needed
5. Click **Generate Report**
6. Click **Export to CSV** to save the report

## Implementing Actual Database Connection

The current implementation is a **placeholder**. To implement actual database connectivity:

### 1. Edit `db_integration.py`

Open `db_integration.py` and implement the TODO sections:

```python
def connect(self) -> bool:
    """Establish connection to database"""

    if self.db_type == "mssql":
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password}"
        )
        self.connection = pyodbc.connect(conn_str)
        return True

    elif self.db_type == "mysql":
        import pymysql
        self.connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=self.database
        )
        return True

    # Add other database types...

    return False
```

### 2. Implement Query Methods

For JobBOSS integration, implement the query methods in `JobBOSSIntegration` class:

```python
def get_new_jobs(self, since_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Get newly created jobs from JobBOSS"""

    if not since_date:
        since_date = datetime.now().replace(hour=0, minute=0, second=0)

    cursor = self.connection.cursor()

    # Example query - adjust table/column names to match your JobBOSS schema
    query = """
        SELECT
            j.Job AS job_number,
            c.Customer AS customer,
            j.Description AS description,
            j.Created_Date AS created_date
        FROM Job j
        JOIN Customer c ON j.Customer = c.Customer
        WHERE j.Created_Date >= ?
        ORDER BY j.Created_Date DESC
    """

    cursor.execute(query, (since_date,))

    jobs = []
    for row in cursor.fetchall():
        jobs.append({
            'job_number': row.job_number,
            'customer': row.customer,
            'description': row.description,
            'created_date': row.created_date
        })

    return jobs
```

### 3. Update JobDocs-qt.py Methods

Update the placeholder methods in `JobDocs-qt.py`:

```python
def connect_to_database(self):
    """Connect to database using settings"""
    from db_integration import JobBOSSIntegration

    try:
        self.db_connection = JobBOSSIntegration(
            host=self.settings.get('db_host'),
            port=self.settings.get('db_port'),
            database=self.settings.get('db_name'),
            username=self.settings.get('db_username'),
            password=self.settings.get('db_password')
        )

        success, message = self.db_connection.test_connection()

        if success:
            self.db_status_label.setText(f"Status: Connected")
            self.db_status_label.setStyleSheet("color: green;")
            self.connect_db_btn.setEnabled(False)
            self.disconnect_db_btn.setEnabled(True)
        else:
            raise Exception(message)

    except Exception as e:
        QMessageBox.critical(self, "Connection Failed", f"Failed to connect:\n{str(e)}")
```

## Auto-Launching JobDocs for New Jobs

To automatically open JobDocs when a new job is created in JobBOSS:

### Option 1: Polling Service

Create a background service that polls the database:

```python
from db_integration import JobWatcher, JobBOSSIntegration
import subprocess

# Create connection
jobboss = JobBOSSIntegration(...)

# Define callback
def on_new_job(job):
    # Launch JobDocs with job data
    subprocess.Popen([
        'python', 'JobDocs-qt.py',
        '--job-number', job['job_number'],
        '--customer', job['customer'],
        '--description', job['description']
    ])

# Start watcher
watcher = JobWatcher(jobboss)
watcher.start_watching(interval_seconds=60, callback=on_new_job)
```

### Option 2: Database Trigger

Create a SQL Server trigger that calls an external script:

```sql
CREATE TRIGGER JobCreated
ON Job
AFTER INSERT
AS
BEGIN
    DECLARE @JobNumber VARCHAR(50)
    DECLARE @Customer VARCHAR(100)

    SELECT @JobNumber = Job, @Customer = Customer
    FROM inserted

    -- Call external script
    EXEC xp_cmdshell 'python C:\path\to\launch_jobdocs.py ' + @JobNumber
END
```

## Security Considerations

⚠️ **CRITICAL SECURITY WARNINGS:**

1. **Password Storage - INSECURE BY DEFAULT**:
   - ❌ Passwords are currently stored in **PLAIN TEXT** in `settings.json`
   - ❌ **DO NOT USE IN PRODUCTION** without implementing secure storage
   - ✅ For production, implement one of these solutions:
     - Use Windows Credential Manager: `pip install keyring`
     - Use environment variables
     - Use a secrets management service (Azure Key Vault, AWS Secrets Manager, etc.)
   - Location of settings.json:
     - Windows: `C:\Users\<Username>\AppData\Local\JobDocs\settings.json`
     - macOS: `~/Library/Application Support/JobDocs/settings.json`
     - Linux: `~/.local/share/JobDocs/settings.json`

2. **Database Permissions - PRINCIPLE OF LEAST PRIVILEGE**:
   - Create a dedicated read-only database user for JobDocs
   - Grant only SELECT permissions on required tables
   - Never use database admin credentials
   - Document the minimum required permissions

3. **SQL Injection Prevention**:
   - The placeholder code uses parameterized queries
   - **Always** use parameterized queries, never string concatenation
   - Example (SAFE): `cursor.execute("SELECT * FROM Job WHERE Job = ?", (job_number,))`
   - Example (UNSAFE): `cursor.execute(f"SELECT * FROM Job WHERE Job = '{job_number}'")`

4. **Network Security**:
   - Use SSL/TLS for database connections when connecting over network
   - Use VPN or SSH tunneling for connections over untrusted networks
   - Restrict database access by IP address if possible
   - Use Windows Authentication (trusted connection) when available on SQL Server

5. **Audit Logging**:
   - Consider enabling database audit logging for all JobDocs queries
   - Log connection attempts and failures
   - Monitor for suspicious query patterns

## JobBOSS Schema Information

Common JobBOSS tables (names may vary by version):
- `Job` - Main job information
- `Customer` - Customer data
- `Job_Operation` - Job operations/routing
- `Material_Req` - Material requirements
- `Delivery` - Delivery information

Consult your JobBOSS documentation or database schema for exact table and column names.

## Troubleshooting

### "Module not found" error
Install the required database driver (see Step 2 above)

### Connection timeout
- Check host and port settings
- Verify database server is accessible
- Check firewall settings
- Test connection with a database tool (SQL Server Management Studio, MySQL Workbench, etc.)

### Authentication failed
- Verify username and password
- Check if the database user has appropriate permissions
- For SQL Server, check if SQL authentication is enabled (not just Windows auth)

### ODBC Driver not found (SQL Server)
Install the ODBC Driver:
- **Windows**: Download "ODBC Driver 17 for SQL Server" or "ODBC Driver 18 for SQL Server" from Microsoft
  - https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- **Linux**: Install via package manager
  ```bash
  # Ubuntu/Debian
  sudo apt-get install unixodbc-dev

  # Red Hat/CentOS
  sudo yum install unixODBC-devel
  ```
- **macOS**: Install via Homebrew
  ```bash
  brew install unixodbc
  ```
- Or use an older driver version in the connection string: `DRIVER={SQL Server}` (not recommended)

## Next Steps

1. Enable experimental features
2. Configure database connection
3. Install database driver
4. Implement actual database queries in `db_integration.py`
5. Test connection
6. Customize queries for your specific database schema
7. Set up auto-launch if desired

## Support

For questions or issues:
- GitHub: https://github.com/i-machine-things/JobDocs
- Check `db_integration.py` for example code and documentation
