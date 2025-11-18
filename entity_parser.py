"""
Entity Parser - Extract entities from natural language
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

# Setup logging
logger = logging.getLogger(__name__)


class EntityParser:
    """Parse and extract entities from user messages"""

    def parse_message(
        self,
        message: str,
        allowed_merchant_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Parse user message and extract all possible entities

        Args:
            message: User message text
            allowed_merchant_ids: List of merchants user can access (None = admin mode)

        Returns dict with extracted entities or error
        """
        message_lower = message.lower()
        entities = {}

        # Extract merchant_id
        merchant_id = self._extract_merchant_id(message)
        if merchant_id:
            # Validate merchant access if restrictions exist
            if allowed_merchant_ids is not None:
                if merchant_id not in allowed_merchant_ids:
                    # Return error instead of merchant
                    entities["_merchant_error"] = merchant_id
                    entities["_allowed_merchants"] = allowed_merchant_ids
                    return entities  # Stop parsing, return error

            entities["merchant_id"] = merchant_id

        # Extract report type
        report_type = self._extract_report_type(message_lower)
        if report_type:
            entities["report_type"] = report_type

        # Extract status filter
        status_filter = self._extract_status_filter(message_lower)
        if status_filter:
            entities["status_filter"] = status_filter

        # Extract date range
        date_range = self._extract_date_range(message_lower)
        if date_range:
            entities["date_range"] = date_range

        # Extract output format
        output_format = self._extract_output_format(message_lower)
        if output_format:
            entities["output_format"] = output_format

        # Extract cron and timezone
        cron_data = self._extract_schedule(message_lower)
        if cron_data:
            entities.update(cron_data)

        # Extract email recipients
        emails = self._extract_emails(message)
        if emails:
            entities["email_recipients"] = emails

        return entities

    def _extract_merchant_id(self, message: str) -> Optional[str]:
        """Extract merchant ID (e.g., FINPAY770, TEST_DEBUG, COMP_A, MERCHANT001)"""
        # Keywords that indicate a merchant ID follows
        keyword_patterns = [
            r'\bmid[:\s]+([A-Z0-9_-]{3,})',  # mid: finpay770 or mid TEST_DEBUG
            r'merchant\s*id[:\s]+([A-Z0-9_-]{3,})',  # merchant id: anything
            r'\bmerchant\s+([A-Z0-9_-]{3,})',  # merchant TEST_DEBUG
            r'\bmid\s+([A-Z0-9_-]{3,})',  # mid TEST_DEBUG
        ]

        # Try keyword-based extraction first (higher priority)
        for pattern in keyword_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                merchant = match.group(1).upper()
                # Filter common keywords and Indonesian question words
                if merchant not in ['ID', 'TYPE', 'STATUS', 'FORMAT', 'YANG', 'APA', 'BISA', 'AJA', 'SAJA']:
                    return merchant

        # Pattern-based extraction (look for uppercase patterns in the message)
        pattern_extraction = [
            r'\b([A-Z]{3,}[0-9]{2,})\b',  # FINPAY770, ABC123 (letters + numbers)
            r'\b([A-Z][A-Z0-9_-]{4,})\b',  # TEST_DEBUG, COMP_A (uppercase start + chars)
            r'\b([0-9]{5,})\b',  # Pure numbers: 1234567890
        ]

        for pattern in pattern_extraction:
            matches = re.findall(pattern, message)
            for merchant in matches:
                merchant = merchant.upper()
                # Filter out common keywords and Indonesian question words
                if merchant not in ['REPORT', 'TRANSAKSI', 'LAPORAN', 'EXCEL', 'HARIAN',
                                   'SETIAP', 'UNTUK', 'DENGAN', 'FORMAT', 'KIRIM',
                                   'EMAIL', 'HARI', 'BULAN', 'TAHUN', 'TANGGAL',
                                   'YANG', 'APA', 'BISA', 'AJA', 'SAJA', 'MERCHANT']:
                    return merchant

        return None

    def _extract_report_type(self, message: str) -> Optional[str]:
        """Extract report type"""
        if any(word in message for word in ["transaksi", "transaction", "payment", "pembayaran"]):
            return "transaction"
        if any(word in message for word in ["settlement", "settle"]):
            return "settlement"
        if any(word in message for word in ["refund"]):
            return "refund"

        return None

    def _extract_status_filter(self, message: str) -> Optional[List[str]]:
        """Extract status filter from message"""
        # Success patterns
        if any(word in message for word in ["sukses", "success", "berhasil", "successful", "paid", "captured"]):
            return ["PAID", "CAPTURED"]

        # Failed patterns
        if any(word in message for word in ["gagal", "failed", "failure", "expired", "cancel"]):
            return ["FAILED", "EXPIRED", "CANCELLED"]

        # All transactions
        if any(word in message for word in ["semua", "all", "seluruh"]):
            return ["ALL"]

        return None

    def _extract_date_range(self, message: str) -> Optional[str]:
        """Extract date range"""
        # 7 days
        if any(phrase in message for phrase in ["7 hari", "seminggu", "last 7 days", "past 7 days", "7 day"]):
            return "last_7_days"

        # 30 days
        if any(phrase in message for phrase in ["30 hari", "sebulan", "last 30 days", "past 30 days", "30 day", "last month"]):
            return "last_30_days"

        # This week
        if any(phrase in message for phrase in ["minggu ini", "this week"]):
            return "this_week"

        # Last week
        if any(phrase in message for phrase in ["minggu lalu", "last week"]):
            return "last_week"

        # This month
        if any(phrase in message for phrase in ["bulan ini", "this month"]):
            return "this_month"

        # Today
        if any(phrase in message for phrase in ["hari ini", "today"]):
            return "today"

        # Yesterday
        if any(phrase in message for phrase in ["kemarin", "yesterday"]):
            return "yesterday"

        return None

    def _extract_output_format(self, message: str) -> Optional[str]:
        """Extract output format"""
        if any(word in message for word in ["excel", "xlsx", ".xlsx"]):
            return "xlsx"
        if any(word in message for word in ["csv", ".csv"]):
            return "csv"
        if any(word in message for word in ["pdf", ".pdf"]):
            return "pdf"

        return None

    def _extract_schedule(self, message: str) -> Optional[Dict]:
        """Extract cron schedule and timezone"""
        result = {}

        # Extract timezone first
        timezone = self._extract_timezone(message)
        if timezone:
            result["timezone"] = timezone
        else:
            result["timezone"] = "Asia/Jakarta"  # Default

        # Extract cron expression
        cron = self._extract_cron(message)
        if cron:
            result["cron_schedule"] = cron

        return result if "cron_schedule" in result else None

    def _extract_timezone(self, message: str) -> Optional[str]:
        """Extract timezone from message"""
        if "wib" in message:
            return "Asia/Jakarta"
        if "wita" in message:
            return "Asia/Makassar"
        if "wit" in message:
            return "Asia/Jayapura"

        return None

    def _extract_cron(self, message: str) -> Optional[str]:
        """
        Extract cron expression from natural language

        Examples:
        - "setiap hari jam 8" → "0 8 * * *"
        - "every day at 8am" → "0 8 * * *"
        - "setiap senin jam 9" → "0 9 * * 1"
        - "setiap hari kamis jam 8" → "0 8 * * 4"
        - "every monday at 9" → "0 9 * * 1"
        - "setiap 5 menit" → "*/5 * * * *"
        - "0 8 * * 4" → "0 8 * * 4" (direct cron)
        """
        logger.info(f"[EXTRACT_CRON] Processing message: '{message}'")

        # PRIORITY 1: Direct cron expression (user specifies exact cron)
        # Pattern: 5 parts separated by spaces (minute hour day month weekday)
        cron_pattern = r'\b(\d+|\*|[\*/\-,0-9]+)\s+(\d+|\*|[\*/\-,0-9]+)\s+(\d+|\*|[\*/\-,0-9]+)\s+(\d+|\*|[\*/\-,0-9]+)\s+(\d+|\*|[\*/\-,0-9]+)\b'
        cron_match = re.search(cron_pattern, message)
        if cron_match:
            result = f"{cron_match.group(1)} {cron_match.group(2)} {cron_match.group(3)} {cron_match.group(4)} {cron_match.group(5)}"
            logger.critical(f"[EXTRACT_CRON] Direct cron found: '{message}' → '{result}'")
            return result

        # PRIORITY 2: Every X minutes
        if re.search(r'setiap (\d+) menit', message) or re.search(r'every (\d+) minute', message):
            match = re.search(r'setiap (\d+) menit|every (\d+) minute', message)
            minutes = match.group(1) or match.group(2)
            return f"*/{minutes} * * * *"

        # PRIORITY 3: Every X hours
        if re.search(r'setiap (\d+) jam', message) or re.search(r'every (\d+) hour', message):
            match = re.search(r'setiap (\d+) jam|every (\d+) hour', message)
            hours = match.group(1) or match.group(2)
            return f"0 */{hours} * * *"

        # PRIORITY 4: Specific day of week with time (BEFORE daily patterns)
        # Must check this BEFORE "setiap hari" to avoid false matches
        day_patterns = [
            # "weekly" or "mingguan" suffix patterns
            (r'senin\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 1"),
            (r'selasa\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 2"),
            (r'rabu\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 3"),
            (r'kamis\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 4"),
            (r'jumat\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 5"),
            (r'sabtu\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 6"),
            (r'minggu\s+(?:weekly|mingguan)\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 0"),
            # "weekly" or "mingguan" prefix patterns
            (r'(?:weekly|mingguan)\s+senin\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 1"),
            (r'(?:weekly|mingguan)\s+selasa\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 2"),
            (r'(?:weekly|mingguan)\s+rabu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 3"),
            (r'(?:weekly|mingguan)\s+kamis\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 4"),
            (r'(?:weekly|mingguan)\s+jumat\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 5"),
            (r'(?:weekly|mingguan)\s+sabtu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 6"),
            (r'(?:weekly|mingguan)\s+minggu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 0"),
            # Indonesian patterns - with optional "hari" word
            (r'setiap\s+(?:hari\s+)?senin\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 1"),
            (r'setiap\s+(?:hari\s+)?selasa\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 2"),
            (r'setiap\s+(?:hari\s+)?rabu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 3"),
            (r'setiap\s+(?:hari\s+)?kamis\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 4"),
            (r'setiap\s+(?:hari\s+)?jumat\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 5"),
            (r'setiap\s+(?:hari\s+)?sabtu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 6"),
            (r'setiap\s+(?:hari\s+)?minggu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 0"),
            # Alternative patterns
            (r'(?:tiap|every)\s+(?:hari\s+)?senin\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 1"),
            (r'(?:tiap|every)\s+(?:hari\s+)?selasa\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 2"),
            (r'(?:tiap|every)\s+(?:hari\s+)?rabu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 3"),
            (r'(?:tiap|every)\s+(?:hari\s+)?kamis\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 4"),
            (r'(?:tiap|every)\s+(?:hari\s+)?jumat\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 5"),
            (r'(?:tiap|every)\s+(?:hari\s+)?sabtu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 6"),
            (r'(?:tiap|every)\s+(?:hari\s+)?minggu\s+(?:jam\s+)?(\d+)', lambda h: f"0 {h} * * 0"),
            # English patterns
            (r'every\s+monday\s+at\s+(\d+)', lambda h: f"0 {h} * * 1"),
            (r'every\s+tuesday\s+at\s+(\d+)', lambda h: f"0 {h} * * 2"),
            (r'every\s+wednesday\s+at\s+(\d+)', lambda h: f"0 {h} * * 3"),
            (r'every\s+thursday\s+at\s+(\d+)', lambda h: f"0 {h} * * 4"),
            (r'every\s+friday\s+at\s+(\d+)', lambda h: f"0 {h} * * 5"),
            (r'every\s+saturday\s+at\s+(\d+)', lambda h: f"0 {h} * * 6"),
            (r'every\s+sunday\s+at\s+(\d+)', lambda h: f"0 {h} * * 0"),
            # Just day name with hour (no "setiap")
            (r'\bsenin\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 1"),
            (r'\bselasa\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 2"),
            (r'\brabu\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 3"),
            (r'\bkamis\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 4"),
            (r'\bjumat\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 5"),
            (r'\bsabtu\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 6"),
            (r'\bminggu\s+(?:jam\s+)?(\d+)\b', lambda h: f"0 {h} * * 0"),
        ]

        for pattern, cron_func in day_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                hour = match.group(1)
                result = cron_func(hour)
                logger.critical(f"[EXTRACT_CRON] Day pattern matched: '{message}' → '{result}' (pattern: {pattern})")
                return result

        # PRIORITY 5: Every day at specific hour (only if no day of week matched)
        daily_patterns = [
            (r'setiap hari jam (\d+)', lambda h: f"0 {h} * * *"),
            (r'every day at (\d+)', lambda h: f"0 {h} * * *"),
            (r'daily at (\d+)', lambda h: f"0 {h} * * *"),
            (r'jam (\d+) setiap hari', lambda h: f"0 {h} * * *"),
            (r'tiap hari jam (\d+)', lambda h: f"0 {h} * * *"),
        ]

        for pattern, cron_func in daily_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                hour = match.group(1)
                return cron_func(hour)

        # PRIORITY 6: Monthly schedules
        monthly_patterns = [
            # Indonesian variations with "tgl" abbreviation (with hour)
            (r'setiap tgl (\d+) (?:setiap |tiap |di )?bulan jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tiap tgl (\d+) (?:setiap |tiap |di )?bulan jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'setiap tgl (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tiap tgl (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            # WITHOUT hour - default to 8am
            (r'setiap tgl (\d+)(?: (?:setiap |tiap |di )?bulan)?', lambda d: f"0 8 {d} * *"),
            (r'tiap tgl (\d+)(?: (?:setiap |tiap |di )?bulan)?', lambda d: f"0 8 {d} * *"),
            (r'tgl (\d+)(?: (?:setiap |tiap |di )?bulan)?', lambda d: f"0 8 {d} * *"),
            # Indonesian variations with full "tanggal" (with hour)
            (r'setiap tanggal (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tiap tanggal (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tanggal (\d+) setiap bulan jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tanggal (\d+) tiap bulan jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            # WITHOUT hour - default to 8am
            (r'setiap tanggal (\d+)', lambda d: f"0 8 {d} * *"),
            (r'tiap tanggal (\d+)', lambda d: f"0 8 {d} * *"),
            (r'tanggal (\d+) tiap bulan', lambda d: f"0 8 {d} * *"),
            (r'tanggal (\d+) setiap bulan', lambda d: f"0 8 {d} * *"),
            (r'bulanan tanggal (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'monthly tanggal (\d+) jam (\d+)', lambda d, h: f"0 {h} {d} * *"),
            # English variations
            (r'every (\d+)(?:st|nd|rd|th)? at (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'monthly on (\d+)(?:st|nd|rd|th)? at (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'(\d+)(?:st|nd|rd|th)? of every month at (\d+)', lambda d, h: f"0 {h} {d} * *"),
            # Without explicit "jam"
            (r'setiap tanggal (\d+) pukul (\d+)', lambda d, h: f"0 {h} {d} * *"),
            (r'tanggal (\d+) pukul (\d+)', lambda d, h: f"0 {h} {d} * *"),
            # Generic monthly (assume 1st of month at specified hour)
            (r'bulanan jam (\d+)', lambda h: f"0 {h} 1 * *"),
            (r'monthly at (\d+)', lambda h: f"0 {h} 1 * *"),
        ]

        for pattern, cron_func in monthly_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    result = cron_func(match.group(1), match.group(2))
                elif len(groups) == 1:
                    result = cron_func(match.group(1))
                else:
                    continue
                logger.critical(f"[EXTRACT_CRON] Monthly pattern matched: '{message}' → '{result}'")
                return result

        # PRIORITY 7: Generic time phrases (LAST RESORT - no specific day mentioned)
        # Only use if message doesn't contain day names
        day_keywords = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu', 'minggu',
                       'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        has_day_keyword = any(day in message.lower() for day in day_keywords)

        if not has_day_keyword:
            if "pagi" in message or "morning" in message:
                logger.critical(f"[EXTRACT_CRON] Generic 'pagi' fallback: '{message}' → '0 8 * * *' (NO day keyword found)")
                return "0 8 * * *"  # Default morning = 8am daily
            if "siang" in message or "noon" in message:
                logger.critical(f"[EXTRACT_CRON] Generic 'siang' fallback: '{message}' → '0 12 * * *'")
                return "0 12 * * *"
            if "sore" in message or "afternoon" in message:
                logger.critical(f"[EXTRACT_CRON] Generic 'sore' fallback: '{message}' → '0 17 * * *'")
                return "0 17 * * *"
            if "malam" in message or "night" in message:
                logger.critical(f"[EXTRACT_CRON] Generic 'malam' fallback: '{message}' → '0 20 * * *'")
                return "0 20 * * *"
        else:
            logger.warning(f"[EXTRACT_CRON] Day keyword found but no pattern matched: '{message}' (keywords: {[k for k in day_keywords if k in message.lower()]})")

        logger.warning(f"[EXTRACT_CRON] No pattern matched: '{message}' → None")
        return None

    def _extract_emails(self, message: str) -> Optional[List[str]]:
        """Extract email addresses from message"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, message)

        if emails:
            return [email.strip() for email in emails]

        return None


# Quick test
if __name__ == "__main__":
    parser = EntityParser()

    # Test cases
    test_messages = [
        "buatkan report transaksi sukses untuk mid finpay770",
        "7 hari terakhir format excel",
        "setiap hari jam 8 pagi wib",
        "kirim ke finance@finpay.com dan manager@finpay.com",
        "buatkan report transaksi sukses untuk mid finpay770, 7 hari terakhir, excel, setiap hari jam 8, kirim ke finance@finpay.com"
    ]

    for msg in test_messages:
        print(f"\n📝 Message: {msg}")
        result = parser.parse_message(msg)
        print(f"✅ Extracted: {result}")

    print("\n✅ All parser tests completed!")
