"""
Cron Converter - Convert cron expressions to human-readable format
Supports Indonesian and English languages
"""

class CronConverter:
    """Convert cron expressions to human-readable schedules"""

    def __init__(self):
        # Day names mapping
        self.days_id = {
            "0": "Minggu",
            "1": "Senin",
            "2": "Selasa",
            "3": "Rabu",
            "4": "Kamis",
            "5": "Jumat",
            "6": "Sabtu"
        }

        self.days_en = {
            "0": "Sunday",
            "1": "Monday",
            "2": "Tuesday",
            "3": "Wednesday",
            "4": "Thursday",
            "5": "Friday",
            "6": "Saturday"
        }

        # Month names mapping
        self.months_id = {
            "1": "Januari", "2": "Februari", "3": "Maret", "4": "April",
            "5": "Mei", "6": "Juni", "7": "Juli", "8": "Agustus",
            "9": "September", "10": "Oktober", "11": "November", "12": "Desember"
        }

        self.months_en = {
            "1": "January", "2": "February", "3": "March", "4": "April",
            "5": "May", "6": "June", "7": "July", "8": "August",
            "9": "September", "10": "October", "11": "November", "12": "December"
        }

    def to_readable(self, cron_expr: str, language: str = "id") -> str:
        """
        Convert cron expression to human-readable format

        Args:
            cron_expr: Cron expression (e.g., "0 8 * * 4")
            language: Language code ("id" or "en")

        Returns:
            Human-readable schedule description

        Examples:
            "0 8 * * 4" → "Setiap hari Kamis jam 08:00"
            "0 8 1 * *" → "Setiap tanggal 1 jam 08:00"
            "0 8 * * *" → "Setiap hari jam 08:00"
        """
        if not cron_expr or not isinstance(cron_expr, str):
            return cron_expr

        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return cron_expr  # Invalid cron, return as-is

        minute, hour, day, month, weekday = parts

        # Format time
        time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"

        if language == "id":
            return self._to_readable_id(minute, hour, day, month, weekday, time_str)
        else:
            return self._to_readable_en(minute, hour, day, month, weekday, time_str)

    def _to_readable_id(self, minute: str, hour: str, day: str, month: str, weekday: str, time_str: str) -> str:
        """Convert to Indonesian readable format"""

        # Weekly schedule (specific day of week)
        if weekday != "*":
            day_name = self.days_id.get(weekday, f"hari ke-{weekday}")
            return f"Setiap hari {day_name} jam {time_str}"

        # Monthly schedule (specific day of month)
        if day != "*":
            # Specific month and day
            if month != "*":
                month_name = self.months_id.get(month, f"bulan ke-{month}")
                return f"Setiap tanggal {day} {month_name} jam {time_str}"
            # Any month, specific day
            return f"Setiap tanggal {day} jam {time_str}"

        # Yearly schedule (specific month)
        if month != "*":
            month_name = self.months_id.get(month, f"bulan ke-{month}")
            return f"Setiap bulan {month_name} jam {time_str}"

        # Daily schedule
        return f"Setiap hari jam {time_str}"

    def _to_readable_en(self, minute: str, hour: str, day: str, month: str, weekday: str, time_str: str) -> str:
        """Convert to English readable format"""

        # Weekly schedule (specific day of week)
        if weekday != "*":
            day_name = self.days_en.get(weekday, f"day {weekday}")
            return f"Every {day_name} at {time_str}"

        # Monthly schedule (specific day of month)
        if day != "*":
            # Specific month and day
            if month != "*":
                month_name = self.months_en.get(month, f"month {month}")
                return f"Every {month_name} {self._ordinal(day)} at {time_str}"
            # Any month, specific day
            return f"Every {self._ordinal(day)} of the month at {time_str}"

        # Yearly schedule (specific month)
        if month != "*":
            month_name = self.months_en.get(month, f"month {month}")
            return f"Every {month_name} at {time_str}"

        # Daily schedule
        return f"Every day at {time_str}"

    def _ordinal(self, day: str) -> str:
        """Convert day number to ordinal (1st, 2nd, 3rd, etc.)"""
        day_int = int(day)
        if 10 <= day_int % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_int % 10, "th")
        return f"{day_int}{suffix}"

    def to_readable_with_cron(self, cron_expr: str, language: str = "id") -> str:
        """
        Convert to readable format with cron expression included

        Args:
            cron_expr: Cron expression
            language: Language code ("id" or "en")

        Returns:
            Readable format with cron expression in parentheses

        Example:
            "0 8 * * 4" → "Setiap hari Kamis jam 08:00 (cron: 0 8 * * 4)"
        """
        readable = self.to_readable(cron_expr, language)
        return f"{readable} (cron: {cron_expr})"


# Singleton instance
_converter = CronConverter()

def to_readable(cron_expr: str, language: str = "id") -> str:
    """
    Convenience function to convert cron to readable format

    Args:
        cron_expr: Cron expression
        language: Language code ("id" or "en")

    Returns:
        Human-readable schedule description
    """
    return _converter.to_readable(cron_expr, language)


def to_readable_with_cron(cron_expr: str, language: str = "id") -> str:
    """
    Convenience function to convert cron to readable format with cron expression

    Args:
        cron_expr: Cron expression
        language: Language code ("id" or "en")

    Returns:
        Readable format with cron expression
    """
    return _converter.to_readable_with_cron(cron_expr, language)


# For testing
if __name__ == "__main__":
    converter = CronConverter()

    test_cases = [
        ("0 8 * * 4", "id", "Setiap hari Kamis jam 08:00"),
        ("0 8 1 * *", "id", "Setiap tanggal 1 jam 08:00"),
        ("0 8 * * *", "id", "Setiap hari jam 08:00"),
        ("0 9 15 * *", "id", "Setiap tanggal 15 jam 09:00"),
        ("0 8 * * 1", "id", "Setiap hari Senin jam 08:00"),
        ("30 14 * * 5", "id", "Setiap hari Jumat jam 14:30"),
        ("0 8 * * 4", "en", "Every Thursday at 08:00"),
        ("0 8 1 * *", "en", "Every 1st of the month at 08:00"),
        ("0 8 15 * *", "en", "Every 15th of the month at 08:00"),
    ]

    print("🧪 Testing CronConverter:\n")
    all_passed = True

    for cron, lang, expected in test_cases:
        result = converter.to_readable(cron, lang)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False

        print(f"{status} {cron} ({lang})")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")
        print()

    if all_passed:
        print("✅✅✅ All tests PASSED!")
    else:
        print("❌ Some tests FAILED")

    # Test with cron expression included
    print("\n📋 With cron expression:")
    print(converter.to_readable_with_cron("0 8 * * 4", "id"))
    print(converter.to_readable_with_cron("0 8 1 * *", "id"))
