"""
Payload Builder - Build JSON payload for /schedules/complete API
"""
import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class PayloadBuilder:
    """Build complete schedule payload for Go API"""

    def __init__(self):
        self.default_datasource_id = int(os.getenv("DEFAULT_DATASOURCE_ID", "13"))
        self.default_timezone = os.getenv("DEFAULT_TIMEZONE", "Asia/Jakarta")
        self.default_timeout = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "300"))
        self.default_max_rows = int(os.getenv("DEFAULT_MAX_ROWS", "10000"))
        self.default_max_retry = int(os.getenv("DEFAULT_MAX_RETRY", "3"))
        self.default_retry_interval = int(os.getenv("DEFAULT_RETRY_INTERVAL_MINUTES", "5"))

    def build_payload(self, collected_data: Dict, user_id: str = "ai-assistant") -> Dict:
        """
        Build complete payload for POST /api/schedules/complete

        Args:
            collected_data: Data collected from conversation
            user_id: User ID for created_by/updated_by fields

        Returns:
            Complete JSON payload
        """
        # Auto-calculate date_range if not provided
        if "date_range" not in collected_data or not collected_data["date_range"]:
            cron = collected_data.get("cron_schedule", "")
            collected_data["date_range"] = self._auto_calculate_date_range(cron)

        # Generate report name
        report_name = self._generate_report_name(collected_data)

        # Generate SQL query
        report_query = self._generate_sql_query(collected_data)

        # Build payload
        payload = {
            "cron_expression": collected_data.get("cron_schedule", "0 8 * * *"),
            "timezone": collected_data.get("timezone", self.default_timezone),
            "is_active": True,
            "created_by": user_id,
            "updated_by": user_id,
            "configs": {
                "report_name": report_name,
                "report_query": report_query,
                "output_format": collected_data.get("output_format", "xlsx"),
                "datasource_id": self.default_datasource_id,
                "parameters": self._build_parameters(collected_data),
                "timeout_seconds": self.default_timeout,
                "max_rows": self.default_max_rows,
                "deliveries": [
                    self._build_delivery(collected_data, user_id)
                ]
            }
        }

        return payload

    def _auto_calculate_date_range(self, cron_schedule: str) -> str:
        """
        Auto-calculate date_range from cron schedule pattern

        Args:
            cron_schedule: Cron expression (e.g., "0 8 * * *")

        Returns:
            date_range value (e.g., "yesterday", "last_week")
        """
        if not cron_schedule:
            return "yesterday"  # Default

        # Daily: 0 H * * * or */H * * * (every H hours)
        if re.match(r'^\d+ \d+ \* \* \*$', cron_schedule):
            return "yesterday"  # Daily report = yesterday's data

        # Weekly: 0 H * * D (D = day of week 0-6)
        if re.match(r'^\d+ \d+ \* \* [0-6]$', cron_schedule):
            return "last_week"  # Weekly report = last week's data

        # Monthly: 0 H D * * (D = day of month 1-31)
        if re.match(r'^\d+ \d+ \d+ \* \*$', cron_schedule):
            return "last_month"  # Monthly report = last month's data

        # Hourly/frequent (*/H * * * * or 0 */H * * *)
        if '*/' in cron_schedule:
            return "today"  # Frequent reports = today's data

        # Default fallback
        return "yesterday"

    def _generate_report_name(self, collected_data: Dict) -> str:
        """Generate report name from collected data"""
        report_type = collected_data.get("report_type", "Report").capitalize()
        merchant_id = collected_data.get("merchant_id", "Unknown")

        # Determine frequency
        cron = collected_data.get("cron_schedule", "")
        if "* * *" in cron and "*/" not in cron:
            frequency = "Harian"  # Daily
        elif "* * 1" in cron:
            frequency = "Mingguan (Senin)"
        elif "*/" in cron:
            frequency = "Periodik"
        else:
            frequency = "Custom"

        return f"{report_type} {merchant_id} - {frequency}"

    def _generate_sql_query(self, collected_data: Dict) -> str:
        """
        Generate SQL query from collected data

        Note: Filters are applied via parameters.filters, not in SQL WHERE clause
        The executor will apply filters dynamically using apply_filters_to_query()
        """
        # Base query without WHERE clause (filters applied by executor)
        query = """SELECT
    ipg_trx_master.trx_invoice,
    ipg_trx_master.payment_at,
    ipg_trx_master.total_capture_amount,
    ipg_trx_master.payment_status,
    ipg_cust_detail.cust_name,
    ipg_trx_master.payment_channel
FROM ipg_trx_master
LEFT JOIN ipg_cust_detail ON ipg_trx_master.id = ipg_cust_detail.id_parent
ORDER BY ipg_trx_master.payment_at DESC"""

        return query.strip()

    def _get_date_condition(self, date_range: str) -> Optional[str]:
        """Convert date_range to SQL condition"""
        date_conditions = {
            "today": "DATE(ipg_trx_master.payment_at) = CURDATE()",
            "yesterday": "DATE(ipg_trx_master.payment_at) = CURDATE() - INTERVAL 1 DAY",
            "last_7_days": "ipg_trx_master.payment_at >= CURDATE() - INTERVAL 7 DAY",
            "last_30_days": "ipg_trx_master.payment_at >= CURDATE() - INTERVAL 30 DAY",
            "this_week": "YEARWEEK(ipg_trx_master.payment_at, 1) = YEARWEEK(CURDATE(), 1)",
            "last_week": "YEARWEEK(ipg_trx_master.payment_at, 1) = YEARWEEK(CURDATE(), 1) - 1",
            "this_month": "YEAR(ipg_trx_master.payment_at) = YEAR(CURDATE()) AND MONTH(ipg_trx_master.payment_at) = MONTH(CURDATE())",
        }

        return date_conditions.get(date_range)

    def _build_parameters(self, collected_data: Dict) -> Dict:
        """Build parameters JSON field in executor-compatible format"""
        filters = []

        # Add merchant_id filter
        if collected_data.get("merchant_id"):
            filters.append({
                "field": "merchant_id",
                "operator": "=",
                "type": "string",
                "value": collected_data.get("merchant_id")
            })

        # Add status filter
        if collected_data.get("status_filter"):
            filters.append({
                "field": "payment_status",
                "operator": "IN",
                "type": "string",
                "value": collected_data.get("status_filter")
            })

        return {
            "filters": filters,
            "date_field": "payment_at",
            "export_columns": [
                "trx_invoice",
                "payment_at",
                "total_capture_amount",
                "payment_status",
                "cust_name",
                "payment_channel"
            ],
            "export_labels": [
                "Order ID",
                "Payment Date",
                "Amount",
                "Status",
                "Customer Name",
                "Payment Channel"
            ]
        }

    def _build_delivery(self, collected_data: Dict, user_id: str) -> Dict:
        """Build delivery configuration"""
        email_recipients = collected_data.get("email_recipients", [])

        # Determine delivery name
        if len(email_recipients) == 1:
            delivery_name = f"Email ke {email_recipients[0].split('@')[0].title()}"
        else:
            delivery_name = f"Email ke {len(email_recipients)} recipients"

        # Build email config
        delivery_config = {
            "subject": "Report: {{report_name}} - {{execution_date}}",
            "body": """Terlampir report {{report_name}} untuk periode {{date_range}}.

Generated at: {{execution_time}}
Total rows: {{row_count}}
File size: {{file_size}}

---
Automated report from Scheduling Report System"""
        }

        return {
            "delivery_name": delivery_name,
            "method": "email",
            "max_retry": self.default_max_retry,
            "retry_interval_minutes": self.default_retry_interval,
            "is_active": True,
            "delivery_config": delivery_config,
            "recipients": [
                {
                    "recipient_value": email,
                    "is_active": True
                }
                for email in email_recipients
            ]
        }

    def format_payload_preview(self, payload: Dict) -> str:
        """Format payload for display (pretty print)"""
        return json.dumps(payload, indent=2, ensure_ascii=False)


# Quick test
if __name__ == "__main__":
    builder = PayloadBuilder()

    # Test data
    test_data = {
        "merchant_id": "FINPAY770",
        "report_type": "transaction",
        "status_filter": ["PAID", "CAPTURED"],
        "date_range": "last_7_days",
        "output_format": "xlsx",
        "cron_schedule": "0 8 * * *",
        "timezone": "Asia/Jakarta",
        "email_recipients": ["finance@finpay.com", "manager@finpay.com"]
    }

    print("🔨 Building payload...")
    payload = builder.build_payload(test_data, user_id="test@example.com")

    print("\n✅ Generated Payload:")
    print(builder.format_payload_preview(payload))

    print("\n✅ Payload builder test completed!")
