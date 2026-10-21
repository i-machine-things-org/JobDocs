"""Registry of every report type Reports (Beta) can run.

Adding a new report type means writing a new file in this package (a
ReportDefinition, see base.py) and adding it to _ALL below -- nothing in
modules/reporting/module.py or experimental/db_integration.py needs to
change.
"""

from modules.reporting.reports.employee_efficiency import EMPLOYEE_EFFICIENCY_DETAIL, EMPLOYEE_EFFICIENCY_SUMMARY
from modules.reporting.reports.job_report import JOB_REPORT
from modules.reporting.reports.job_statistics import JOB_STATISTICS
from modules.reporting.reports.jobs_by_customer import JOBS_BY_CUSTOMER
from modules.reporting.reports.jobs_by_date_range import JOBS_BY_DATE_RANGE
from modules.reporting.reports.recent_jobs import RECENT_JOBS
from modules.reporting.reports.top_customers import TOP_CUSTOMERS

_ALL = (
    JOB_REPORT,
    JOB_STATISTICS,
    JOBS_BY_CUSTOMER,
    JOBS_BY_DATE_RANGE,
    RECENT_JOBS,
    TOP_CUSTOMERS,
    EMPLOYEE_EFFICIENCY_DETAIL,
    EMPLOYEE_EFFICIENCY_SUMMARY,
)

REPORTS = {r.name: r for r in _ALL}
REPORT_TYPES = tuple(REPORTS)
