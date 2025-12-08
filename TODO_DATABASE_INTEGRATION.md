# Database Integration - Implementation TODO

**Copyright (c) 2025 JobDocs Contributors**
**Licensed under the MIT License - see LICENSE file for details**

This document tracks the tasks needed to implement full database integration with JobBOSS or other ERP systems.

> **Note**: This feature is experimental and requires significant implementation work before production use.

## Phase 1: Basic Database Connectivity ⏳

### Required Dependencies
- [ ] Install database driver
  - [ ] For SQL Server/JobBOSS: `pip install pyodbc`
  - [ ] For MySQL: `pip install pymysql`
  - [ ] For PostgreSQL: `pip install psycopg2-binary`
- [ ] Add driver requirements to `requirements.txt`
- [ ] Document ODBC driver installation (Windows)

### Database Connection Implementation
- [ ] Implement `DatabaseConnection.connect()` in `db_integration.py`
  - [ ] Add MSSQL connection code using pyodbc
  - [ ] Add MySQL connection code using pymysql
  - [ ] Add PostgreSQL connection code using psycopg2
  - [ ] Add proper error handling
  - [ ] Add connection timeout settings
- [ ] Implement `DatabaseConnection.disconnect()`
- [ ] Implement `DatabaseConnection.test_connection()`
- [ ] Add connection pooling for better performance
- [ ] Add retry logic for failed connections

### Security Improvements
- [ ] **CRITICAL**: Remove plain-text password storage
  - [ ] Implement Windows Credential Manager integration (`pip install keyring`)
  - [ ] Add option to use environment variables
  - [ ] Add password encryption in settings file
- [ ] Add SSL/TLS support for database connections
- [ ] Implement read-only database user configuration
- [ ] Add SQL injection prevention validation
- [ ] Document security best practices

## Phase 2: JobBOSS Integration 🔄

### Schema Discovery
- [ ] Document JobBOSS database schema
  - [ ] Identify Job table structure
  - [ ] Identify Customer table structure
  - [ ] Identify related tables (Job_Operation, Material_Req, etc.)
  - [ ] Map column names to JobDocs fields
- [ ] Create schema documentation file
- [ ] Add version detection (JobBOSS schema varies by version)

### Query Implementation
- [ ] Implement `JobBOSSIntegration.get_new_jobs()`
  - [ ] Write SQL query for new jobs
  - [ ] Test with actual JobBOSS database
  - [ ] Add proper date filtering
  - [ ] Handle timezone conversions
- [ ] Implement `JobBOSSIntegration.get_job_details()`
  - [ ] Query all relevant job fields
  - [ ] Join with related tables
  - [ ] Return standardized job dictionary
- [ ] Implement `JobBOSSIntegration.get_drawings_for_job()`
  - [ ] Identify where drawings are stored in JobBOSS
  - [ ] Parse drawing number formats
  - [ ] Handle multiple drawing references
- [ ] Add error handling for missing jobs
- [ ] Add caching to reduce database queries

### Data Mapping
- [ ] Map JobBOSS customer names to JobDocs format
- [ ] Map JobBOSS job numbers to JobDocs format
- [ ] Handle special characters in job/customer names
- [ ] Create data transformation utilities
- [ ] Add validation for required fields

## Phase 3: Job Watching & Auto-Launch 🔍

### Job Monitoring
- [ ] Implement polling service in `JobWatcher.start_watching()`
  - [ ] Set up background thread
  - [ ] Implement configurable polling interval
  - [ ] Add proper thread shutdown
  - [ ] Add logging for monitoring
- [ ] Implement `JobWatcher.stop_watching()`
- [ ] Add callback mechanism for new jobs
- [ ] Create system tray integration (optional)
- [ ] Add notification system for new jobs

### Auto-Launch
- [ ] Add command-line argument parsing to JobDocs-qt.py
  - [ ] `--job-number` parameter
  - [ ] `--customer` parameter
  - [ ] `--description` parameter
  - [ ] `--auto-populate` flag
- [ ] Create launcher script for job watcher
- [ ] Add Windows service installation (optional)
- [ ] Add Linux systemd service file (optional)
- [ ] Document auto-launch setup

### Alternative: Database Triggers
- [ ] Create SQL Server trigger example for Job table
- [ ] Create stored procedure to call external script
- [ ] Document xp_cmdshell configuration
- [ ] Add security considerations for triggers
- [ ] Create rollback/uninstall scripts

## Phase 4: Reporting Features 📊

### Report Generation
- [ ] Implement `ReportGenerator.get_jobs_by_customer()`
  - [ ] Write SQL query
  - [ ] Add sorting options
  - [ ] Add pagination
- [ ] Implement `ReportGenerator.get_jobs_by_date_range()`
  - [ ] Add date validation
  - [ ] Handle timezone issues
  - [ ] Add grouping options
- [ ] Implement `ReportGenerator.get_job_statistics()`
  - [ ] Total job counts
  - [ ] Jobs by time period
  - [ ] Top customers query
  - [ ] Average jobs per customer
- [ ] Add custom query builder for advanced reports
- [ ] Add report templates

### UI Integration
- [ ] Update `connect_to_database()` to use real connection
- [ ] Update `generate_report()` to query actual data
- [ ] Add progress indicator for long queries
- [ ] Add result pagination for large datasets
- [ ] Improve error messages
- [ ] Add report saving/loading
- [ ] Add report scheduling (optional)

### Export Features
- [ ] Enhance CSV export with formatting options
- [ ] Add Excel export (`pip install openpyxl`)
- [ ] Add PDF export (`pip install reportlab`)
- [ ] Add email report feature (optional)
- [ ] Add scheduled export (optional)

## Phase 5: Testing & Quality Assurance ✅

### Unit Tests
- [ ] Create test database with sample data
- [ ] Write tests for `DatabaseConnection` class
- [ ] Write tests for `JobBOSSIntegration` class
- [ ] Write tests for `ReportGenerator` class
- [ ] Write tests for `JobWatcher` class
- [ ] Add mock database for CI/CD
- [ ] Set up automated testing

### Integration Tests
- [ ] Test with actual JobBOSS database (read-only)
- [ ] Test connection error handling
- [ ] Test query performance with large datasets
- [ ] Test concurrent connections
- [ ] Test auto-launch mechanism
- [ ] Test report generation with real data

### Performance Testing
- [ ] Benchmark query performance
- [ ] Optimize slow queries
- [ ] Add query result caching
- [ ] Test with large job histories (10k+ jobs)
- [ ] Profile memory usage
- [ ] Add connection pooling benchmarks

## Phase 6: Documentation & Deployment 📚

### User Documentation
- [ ] Review and update DATABASE_INTEGRATION.md
- [ ] Create video tutorial for setup
- [ ] Add screenshots to documentation
- [ ] Create troubleshooting guide
- [ ] Document common JobBOSS versions and schema differences
- [ ] Add FAQ section

### Developer Documentation
- [ ] Document database schema in code comments
- [ ] Add API documentation for db_integration.py
- [ ] Create architecture diagram
- [ ] Document extension points for other ERP systems
- [ ] Add code examples for common customizations

### Deployment
- [ ] Create installation script
- [ ] Add database driver check to installer
- [ ] Create migration guide from non-DB version
- [ ] Add backup/restore for settings
- [ ] Create uninstall script
- [ ] Test on different Windows/Linux versions

## Phase 7: Additional Features (Future) 🚀

### Advanced Features
- [ ] Support for other ERP systems
  - [ ] SAP integration
  - [ ] Oracle ERP
  - [ ] QuickBooks Enterprise
  - [ ] Custom SQL databases
- [ ] Bi-directional sync (update JobBOSS from JobDocs)
- [ ] Job status updates
- [ ] Material tracking integration
- [ ] Time tracking integration
- [ ] Invoice integration
- [ ] Multi-database support (multiple JobBOSS instances)

### Analytics
- [ ] Dashboard with charts and graphs
- [ ] Trend analysis
- [ ] Predictive analytics
- [ ] Custom KPI tracking
- [ ] Real-time monitoring

## Security Checklist 🔒

- [ ] **Password Storage**: Remove plain-text passwords
- [ ] **SQL Injection**: All queries use parameterized statements
- [ ] **Least Privilege**: Database user has minimal permissions
- [ ] **Encryption**: Connection uses SSL/TLS
- [ ] **Audit Logging**: Log all database operations
- [ ] **Access Control**: Limit who can configure database settings
- [ ] **Secret Management**: Use proper credential storage
- [ ] **Code Review**: Security review of all database code

## Known Issues / Limitations

### Current Limitations
- Passwords stored in plain text in settings.json (MUST FIX before production)
- No connection pooling (may cause performance issues)
- No offline mode (requires active database connection)
- No conflict resolution for bi-directional sync
- Single database connection at a time

### Compatibility Notes
- JobBOSS schema varies by version (needs version detection)
- Some JobBOSS installations use custom fields (needs flexible mapping)
- ODBC driver version matters on Windows (document compatible versions)
- SQL Server authentication vs Windows authentication (need both options)

## Testing Environments

### Development
- [ ] Set up test database with sample JobBOSS data
- [ ] Create dummy job entries for testing
- [ ] Set up local SQL Server Express (free)
- [ ] Create test customer data

### Staging
- [ ] Test with JobBOSS demo database
- [ ] Test with production-like data volume
- [ ] Test with multiple concurrent users

### Production
- [ ] Read-only database user created
- [ ] Connection tested from production environment
- [ ] Backup/rollback plan in place
- [ ] Monitoring configured

## Success Criteria

Phase 1 Complete: ✅
- [x] Can connect to database
- [x] Can test connection
- [x] Passwords stored securely

Phase 2 Complete: ✅
- [x] Can query new jobs from JobBOSS
- [x] Can retrieve job details
- [x] Data maps correctly to JobDocs format

Phase 3 Complete: ✅
- [x] Job watcher monitors for new jobs
- [x] JobDocs auto-launches with job data
- [x] No missed jobs in production use

Phase 4 Complete: ✅
- [x] All report types working
- [x] Export to CSV/Excel working
- [x] Report performance acceptable (<5 seconds)

Ready for Production: ✅
- [x] All security items addressed
- [x] Documentation complete
- [x] Testing complete
- [x] User training complete
- [x] Deployed and monitored for 1 week

## Notes

- Keep database integration **optional** - core JobDocs functionality should work without database
- Maintain backward compatibility with existing settings
- Consider performance impact on JobBOSS database
- Plan for database maintenance windows
- Document any JobBOSS-specific customizations

## Resources

- JobBOSS Documentation: (add link when available)
- SQL Server ODBC Driver: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- Python pyodbc docs: https://github.com/mkleehammer/pyodbc/wiki
- Python keyring docs: https://pypi.org/project/keyring/

---

**Last Updated**: 2025-12-07
**Status**: Planning Phase
**Priority**: Medium (Experimental Feature)
**Owner**: TBD
