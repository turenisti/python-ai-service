"""
Summary Builder - Build human-readable summaries of collected data
For final confirmation before creating scheduled reports
"""
from typing import Dict, Optional
from cron_converter import CronConverter


class SummaryBuilder:
    """Build readable summaries of collected report data"""

    def __init__(self):
        self.cron_converter = CronConverter()

        # Type mappings
        self.report_types_id = {
            "transaction": "Transaksi",
            "settlement": "Settlement",
            "refund": "Refund",
            "payout": "Payout"
        }

        self.report_types_en = {
            "transaction": "Transaction",
            "settlement": "Settlement",
            "refund": "Refund",
            "payout": "Payout"
        }

        # Status mappings
        self.status_map_id = {
            "PAID": "Dibayar",
            "CAPTURED": "Berhasil",
            "FAILED": "Gagal",
            "EXPIRED": "Kadaluarsa",
            "PENDING": "Pending",
            "CANCELLED": "Dibatalkan"
        }

        # Date range mappings
        self.date_range_id = {
            "last_7_days": "7 hari terakhir",
            "last_30_days": "30 hari terakhir",
            "last_week": "Minggu lalu",
            "this_month": "Bulan ini",
            "last_month": "Bulan lalu",
            "this_year": "Tahun ini"
        }

        self.date_range_en = {
            "last_7_days": "Last 7 days",
            "last_30_days": "Last 30 days",
            "last_week": "Last week",
            "this_month": "This month",
            "last_month": "Last month",
            "this_year": "This year"
        }

    def build(self, collected_data: Dict, language: str = "id") -> str:
        """
        Build human-readable summary of collected data

        Args:
            collected_data: Dictionary of collected report configuration
            language: Language code ("id" or "en")

        Returns:
            Formatted summary string

        Example:
            Input: {
                "merchant_id": "FINPAY770",
                "report_type": "transaction",
                "status_filter": ["PAID", "CAPTURED"],
                "date_range": "last_7_days",
                "output_format": "xlsx",
                "cron_schedule": "0 8 * * 4",
                "email_recipients": ["arif@fnnet.co.id"]
            }

            Output (id):
            ✓ Merchant: FINPAY770
            ✓ Jenis Laporan: Transaksi
            ✓ Status: Dibayar, Berhasil
            ✓ Periode: 7 hari terakhir
            ✓ Format: Excel (XLSX)
            ✓ Jadwal: Setiap hari Kamis jam 08:00
            ✓ Email: arif@fnnet.co.id
        """
        if language == "id":
            return self._build_id(collected_data)
        else:
            return self._build_en(collected_data)

    def _build_id(self, data: Dict) -> str:
        """Build Indonesian summary"""
        parts = []

        # Merchant ID
        if data.get('merchant_id'):
            parts.append(f"✓ Merchant: {data['merchant_id']}")

        # Report Type
        if data.get('report_type'):
            report_type = self.report_types_id.get(
                data['report_type'].lower(),
                data['report_type'].title()
            )
            parts.append(f"✓ Jenis Laporan: {report_type}")

        # Status Filter
        if data.get('status_filter'):
            statuses = data['status_filter']
            if isinstance(statuses, str):
                statuses = [s.strip() for s in statuses.split(',')]

            status_labels = [
                self.status_map_id.get(s.upper(), s)
                for s in statuses
            ]
            parts.append(f"✓ Status: {', '.join(status_labels)}")

        # Date Range
        if data.get('date_range'):
            date_range = self.date_range_id.get(
                data['date_range'],
                data['date_range']
            )
            parts.append(f"✓ Periode: {date_range}")

        # Output Format
        if data.get('output_format'):
            format_map = {
                "xlsx": "Excel (XLSX)",
                "csv": "CSV",
                "pdf": "PDF",
                "json": "JSON"
            }
            output_format = format_map.get(
                data['output_format'].lower(),
                data['output_format'].upper()
            )
            parts.append(f"✓ Format: {output_format}")

        # Schedule (with readable format)
        if data.get('cron_schedule'):
            readable = self.cron_converter.to_readable(data['cron_schedule'], "id")
            parts.append(f"✓ Jadwal: {readable}")

        # Timezone
        if data.get('timezone') and data['timezone'] != 'Asia/Jakarta':
            parts.append(f"✓ Zona Waktu: {data['timezone']}")

        # Email Recipients
        if data.get('email_recipients'):
            recipients = data['email_recipients']
            if isinstance(recipients, str):
                recipients = [r.strip() for r in recipients.split(',')]
            parts.append(f"✓ Email: {', '.join(recipients)}")

        return "\n".join(parts) if parts else "Belum ada data yang terkumpul"

    def _build_en(self, data: Dict) -> str:
        """Build English summary"""
        parts = []

        # Merchant ID
        if data.get('merchant_id'):
            parts.append(f"✓ Merchant: {data['merchant_id']}")

        # Report Type
        if data.get('report_type'):
            report_type = self.report_types_en.get(
                data['report_type'].lower(),
                data['report_type'].title()
            )
            parts.append(f"✓ Report Type: {report_type}")

        # Status Filter
        if data.get('status_filter'):
            statuses = data['status_filter']
            if isinstance(statuses, str):
                statuses = [s.strip() for s in statuses.split(',')]
            parts.append(f"✓ Status: {', '.join(statuses)}")

        # Date Range
        if data.get('date_range'):
            date_range = self.date_range_en.get(
                data['date_range'],
                data['date_range']
            )
            parts.append(f"✓ Period: {date_range}")

        # Output Format
        if data.get('output_format'):
            format_map = {
                "xlsx": "Excel (XLSX)",
                "csv": "CSV",
                "pdf": "PDF",
                "json": "JSON"
            }
            output_format = format_map.get(
                data['output_format'].lower(),
                data['output_format'].upper()
            )
            parts.append(f"✓ Format: {output_format}")

        # Schedule (with readable format)
        if data.get('cron_schedule'):
            readable = self.cron_converter.to_readable(data['cron_schedule'], "en")
            parts.append(f"✓ Schedule: {readable}")

        # Timezone
        if data.get('timezone') and data['timezone'] != 'Asia/Jakarta':
            parts.append(f"✓ Timezone: {data['timezone']}")

        # Email Recipients
        if data.get('email_recipients'):
            recipients = data['email_recipients']
            if isinstance(recipients, str):
                recipients = [r.strip() for r in recipients.split(',')]
            parts.append(f"✓ Email: {', '.join(recipients)}")

        return "\n".join(parts) if parts else "No data collected yet"

    def build_compact(self, data: Dict, language: str = "id") -> str:
        """
        Build compact one-line summary

        Args:
            data: Collected data
            language: Language code

        Returns:
            Compact summary string

        Example:
            "Laporan Transaksi FINPAY770 (7 hari terakhir, Excel, setiap Kamis jam 08:00)"
        """
        parts = []

        if language == "id":
            # Report type + merchant
            if data.get('report_type'):
                report_type = self.report_types_id.get(data['report_type'].lower(), data['report_type'])
                parts.append(f"Laporan {report_type}")

            if data.get('merchant_id'):
                parts.append(data['merchant_id'])

            details = []
            if data.get('date_range'):
                date_range = self.date_range_id.get(data['date_range'], data['date_range'])
                details.append(date_range)

            if data.get('output_format'):
                format_map = {"xlsx": "Excel", "csv": "CSV", "pdf": "PDF"}
                details.append(format_map.get(data['output_format'].lower(), data['output_format'].upper()))

            if data.get('cron_schedule'):
                readable = self.cron_converter.to_readable(data['cron_schedule'], "id")
                details.append(readable.lower())

            if details:
                return f"{' '.join(parts)} ({', '.join(details)})"
            else:
                return ' '.join(parts)
        else:
            # English version
            if data.get('report_type'):
                report_type = self.report_types_en.get(data['report_type'].lower(), data['report_type'])
                parts.append(f"{report_type} Report")

            if data.get('merchant_id'):
                parts.append(data['merchant_id'])

            details = []
            if data.get('date_range'):
                date_range = self.date_range_en.get(data['date_range'], data['date_range'])
                details.append(date_range.lower())

            if data.get('output_format'):
                format_map = {"xlsx": "Excel", "csv": "CSV", "pdf": "PDF"}
                details.append(format_map.get(data['output_format'].lower(), data['output_format'].upper()))

            if data.get('cron_schedule'):
                readable = self.cron_converter.to_readable(data['cron_schedule'], "en")
                details.append(readable.lower())

            if details:
                return f"{' '.join(parts)} ({', '.join(details)})"
            else:
                return ' '.join(parts)


# Singleton instance
_builder = SummaryBuilder()


def build_summary(collected_data: Dict, language: str = "id") -> str:
    """
    Convenience function to build summary

    Args:
        collected_data: Dictionary of collected data
        language: Language code

    Returns:
        Formatted summary
    """
    return _builder.build(collected_data, language)


def build_compact_summary(collected_data: Dict, language: str = "id") -> str:
    """
    Convenience function to build compact summary

    Args:
        collected_data: Dictionary of collected data
        language: Language code

    Returns:
        Compact summary
    """
    return _builder.build_compact(collected_data, language)


# For testing
if __name__ == "__main__":
    builder = SummaryBuilder()

    test_data = {
        "merchant_id": "FINPAY770",
        "report_type": "transaction",
        "status_filter": ["PAID", "CAPTURED"],
        "date_range": "last_7_days",
        "output_format": "xlsx",
        "cron_schedule": "0 8 * * 4",
        "timezone": "Asia/Jakarta",
        "email_recipients": ["arif@fnnet.co.id", "test@example.com"]
    }

    print("🧪 Testing SummaryBuilder:\n")
    print("=" * 60)
    print("FULL SUMMARY (Indonesian):")
    print("=" * 60)
    print(builder.build(test_data, "id"))
    print()

    print("=" * 60)
    print("FULL SUMMARY (English):")
    print("=" * 60)
    print(builder.build(test_data, "en"))
    print()

    print("=" * 60)
    print("COMPACT SUMMARY (Indonesian):")
    print("=" * 60)
    print(builder.build_compact(test_data, "id"))
    print()

    print("=" * 60)
    print("COMPACT SUMMARY (English):")
    print("=" * 60)
    print(builder.build_compact(test_data, "en"))
    print()

    # Test with monthly schedule
    test_data_2 = {
        "merchant_id": "MERCHANT_ABC",
        "report_type": "settlement",
        "date_range": "last_30_days",
        "output_format": "csv",
        "cron_schedule": "0 8 1 * *",
        "email_recipients": ["finance@company.com"]
    }

    print("=" * 60)
    print("MONTHLY SCHEDULE SUMMARY (Indonesian):")
    print("=" * 60)
    print(builder.build(test_data_2, "id"))
    print()
