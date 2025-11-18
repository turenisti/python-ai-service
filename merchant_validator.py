"""
Merchant Validator - Validate user access to merchant IDs
"""
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MerchantValidator:
    """Validate merchant access based on user's allowed merchants"""

    def validate_merchant_access(
        self,
        merchant_id: str,
        allowed_merchant_ids: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user can access this merchant

        Args:
            merchant_id: Merchant ID to validate
            allowed_merchant_ids: List of merchant IDs user can access

        Returns:
            (is_valid, error_message)
        """
        # If no restrictions (admin/dev mode), allow all
        if allowed_merchant_ids is None:
            return True, None

        # If empty list, deny all
        if not allowed_merchant_ids:
            return False, "Anda belum memiliki akses ke merchant manapun"

        # Check if merchant in allowed list
        if merchant_id not in allowed_merchant_ids:
            return False, f"Anda tidak memiliki akses ke merchant {merchant_id}"

        return True, None

    def get_merchant_suggestions(
        self,
        allowed_merchant_ids: Optional[List[str]] = None,
        language: str = "id"
    ) -> str:
        """
        Generate AI-friendly merchant list for prompting

        Args:
            allowed_merchant_ids: List of allowed merchants
            language: Response language (id/en)

        Returns:
            Formatted merchant list string
        """
        if not allowed_merchant_ids:
            if language == "id":
                return "Tidak ada merchant yang tersedia"
            return "No merchants available"

        if len(allowed_merchant_ids) == 1:
            if language == "id":
                return f"Merchant ID Anda: {allowed_merchant_ids[0]}"
            return f"Your merchant ID: {allowed_merchant_ids[0]}"

        merchant_list = ", ".join(allowed_merchant_ids)

        if language == "id":
            return f"Merchant ID tersedia: {merchant_list}"
        return f"Available merchant IDs: {merchant_list}"

    def format_error_with_suggestions(
        self,
        error_message: str,
        allowed_merchant_ids: Optional[List[str]] = None,
        language: str = "id"
    ) -> str:
        """
        Format error message with available merchant suggestions

        Args:
            error_message: Base error message
            allowed_merchant_ids: List of allowed merchants
            language: Response language

        Returns:
            Formatted error with suggestions
        """
        suggestions = self.get_merchant_suggestions(allowed_merchant_ids, language)
        return f"{error_message}. {suggestions}"

    def is_admin_mode(self, allowed_merchant_ids: Optional[List[str]]) -> bool:
        """
        Check if running in admin mode (no merchant restrictions)

        Args:
            allowed_merchant_ids: User's allowed merchants

        Returns:
            True if admin mode (None), False otherwise
        """
        return allowed_merchant_ids is None


# Quick test
if __name__ == "__main__":
    validator = MerchantValidator()

    print("Testing MerchantValidator...")

    # Test 1: Valid merchant
    is_valid, error = validator.validate_merchant_access(
        "FINPAY770",
        ["FINPAY770", "MERCHANT001"]
    )
    print(f"\n✓ Test 1 - Valid merchant: {is_valid}, Error: {error}")

    # Test 2: Invalid merchant
    is_valid, error = validator.validate_merchant_access(
        "UNAUTHORIZED",
        ["FINPAY770", "MERCHANT001"]
    )
    print(f"✓ Test 2 - Invalid merchant: {is_valid}, Error: {error}")

    # Test 3: Admin mode (no restrictions)
    is_valid, error = validator.validate_merchant_access(
        "ANY_MERCHANT",
        None  # Admin mode
    )
    print(f"✓ Test 3 - Admin mode: {is_valid}, Error: {error}")

    # Test 4: Suggestions (single merchant)
    suggestions = validator.get_merchant_suggestions(["FINPAY770"])
    print(f"✓ Test 4 - Single merchant suggestions: {suggestions}")

    # Test 5: Suggestions (multiple merchants)
    suggestions = validator.get_merchant_suggestions(["FINPAY770", "MERCHANT001", "MERCHANT002"])
    print(f"✓ Test 5 - Multiple merchant suggestions: {suggestions}")

    # Test 6: Error with suggestions
    error_msg = validator.format_error_with_suggestions(
        "Merchant tidak tersedia",
        ["FINPAY770", "MERCHANT001"]
    )
    print(f"✓ Test 6 - Error with suggestions: {error_msg}")

    print("\n✅ MerchantValidator tests completed!")
