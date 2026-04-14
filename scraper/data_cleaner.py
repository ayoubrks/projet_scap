"""
Data Cleaning Module
Handles deduplication, validation, and normalization of business data.
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DataCleaner:
    """Cleans and validates scraped business data."""

    # Morocco phone number patterns
    MOROCCO_PHONE_PATTERNS = [
        r'^\+212[567]\d{8}$',           # International format: +212XXXXXXXXX
        r'^\+212\s?[567]\d{2}\s?\d{2}\s?\d{2}\s?\d{2}$',  # Spaced international
        r'^0[567]\d{8}$',               # National format: 0XXXXXXXXX
        r'^0[567]\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}$',  # Formatted national
        r'^\+212[\s.-]?[567][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}$',  # Formatted international
    ]

    # Landline patterns
    MOROCCO_LANDLINE_PATTERNS = [
        r'^\+2125\d{8}$',
        r'^05\d{8}$',
        r'^05\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}$',
        r'^\+212[\s.-]?5[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}$',
    ]

    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    URL_PATTERN = re.compile(
        r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/\S*)?$'
    )

    def __init__(self):
        self.stats = {
            'total_input': 0,
            'duplicates_removed': 0,
            'invalid_phones_fixed': 0,
            'invalid_emails_removed': 0,
            'names_normalized': 0,
            'total_output': 0,
        }

    def clean(self, data: List[Dict], progress_callback=None, country: str = "Morocco") -> List[Dict]:
        """
        Clean and validate a list of business records.

        Args:
            data: List of raw business dictionaries
            progress_callback: Optional progress callback
            country: The country of the businesses being cleaned

        Returns:
            Cleaned and validated data
        """
        self.stats['total_input'] = len(data)

        if progress_callback:
            progress_callback("status", f"🧹 Cleaning {len(data)} records for {country}...")

        # Step 1: Normalize all records
        cleaned = []
        for i, record in enumerate(data):
            normalized = self._normalize_record(record, country=country)
            if normalized:
                cleaned.append(normalized)

            if progress_callback and (i + 1) % 10 == 0:
                progress_callback("progress", {
                    "current": i + 1,
                    "total": len(data),
                    "message": f"🧹 Cleaning record {i + 1}/{len(data)}..."
                })

        # Step 2: Remove duplicates
        before_dedup = len(cleaned)
        cleaned = self._remove_duplicates(cleaned)
        self.stats['duplicates_removed'] = before_dedup - len(cleaned)

        # Step 3: Validate and fix data
        validated = []
        for record in cleaned:
            record = self._validate_phone(record)
            record = self._validate_email(record)
            record = self._validate_website(record)
            validated.append(record)

        self.stats['total_output'] = len(validated)

        if progress_callback:
            progress_callback("status",
                f"✅ Cleaning complete: {self.stats['total_output']} records "
                f"({self.stats['duplicates_removed']} duplicates removed)")

        return validated

    def _normalize_record(self, record: Dict, country: str = "Morocco") -> Optional[Dict]:
        """Normalize a single business record."""
        try:
            normalized = {}

            # Normalize name
            name = str(record.get('name', '')).strip()
            if not name or name.lower() in ['', 'n/a', 'none', 'null', 'undefined']:
                return None

            # Capitalize name properly
            normalized['name'] = self._capitalize_name(name)
            self.stats['names_normalized'] += 1

            # Normalize phone
            phone = str(record.get('phone', '')).strip()
            normalized['phone'] = self._normalize_phone(phone, country=country)

            # Normalize email
            email = str(record.get('email', '')).strip().lower()
            normalized['email'] = email if email and email not in ['', 'n/a', 'none'] else ''

            # Normalize website
            website = str(record.get('website', '')).strip()
            normalized['website'] = self._normalize_url(website)

            # Normalize address
            address = str(record.get('address', '')).strip()
            normalized['address'] = self._clean_text(address) if address and address not in ['', 'n/a', 'none'] else ''

            # Normalize city
            city = str(record.get('city', '')).strip()
            normalized['city'] = city.title() if city else ''

            # Category
            category = str(record.get('category', '')).strip()
            normalized['category'] = category.title() if category and category not in ['', 'n/a', 'none'] else ''

            # Geolocation
            normalized['latitude'] = str(record.get('latitude', '')).strip()
            normalized['longitude'] = str(record.get('longitude', '')).strip()

            # Source
            normalized['source'] = str(record.get('source', '')).strip()

            return normalized

        except Exception as e:
            logger.debug(f"Error normalizing record: {e}")
            return None

    def _capitalize_name(self, name: str) -> str:
        """Properly capitalize a business name."""
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()

        # Don't change if it's an acronym (all caps and short)
        if name.isupper() and len(name) <= 10:
            return name

        # Title case with exceptions
        words = name.split()
        capitalized = []
        small_words = {'de', 'du', 'des', 'le', 'la', 'les', 'et', 'en', 'au', 'aux', 'à', 'the', 'and', 'of', 'in'}

        for i, word in enumerate(words):
            if i == 0 or word.lower() not in small_words:
                capitalized.append(word.capitalize())
            else:
                capitalized.append(word.lower())

        return ' '.join(capitalized)

    def _normalize_phone(self, phone: str, country: str = "Morocco") -> str:
        """Normalize phone number based on country."""
        if not phone or phone in ['', 'n/a', 'none', 'None']:
            return ''

        # Remove all non-digit characters except +
        digits = re.sub(r'[^\d+]', '', phone)
        if not digits: return ''

        # Morocco Specific Normalization
        if country == "Morocco":
            if digits.startswith('+212'):
                number = digits[4:]
                if len(number) == 9 and number[0] in '567':
                    return f'+212 {number[0]}{number[1:3]}-{number[3:5]}-{number[5:7]}-{number[7:9]}'
            elif digits.startswith('212'):
                number = digits[3:]
                if len(number) == 9 and number[0] in '567':
                    return f'+212 {number[0]}{number[1:3]}-{number[3:5]}-{number[5:7]}-{number[7:9]}'
            elif digits.startswith('0') and len(digits) == 10:
                number = digits[1:]
                if number[0] in '567':
                    return f'+212 {number[0]}{number[1:3]}-{number[3:5]}-{number[5:7]}-{number[7:9]}'
        
        # Generic/European Normalization
        country_codes = {
            "France": "+33", "Belgium": "+32", "Spain": "+34", 
            "Germany": "+49", "Italy": "+39", "Switzerland": "+41", 
            "United Kingdom": "+44"
        }
        
        code = country_codes.get(country, "")
        if code:
            if digits.startswith(code):
                return digits # Already formatted
            elif digits.startswith('0') and len(digits) >= 9:
                return f"{code} {digits[1:]}"
            elif not digits.startswith('+'):
                return f"{code} {digits}"

        return digits.strip()

    def _validate_phone(self, record: Dict) -> Dict:
        """Validate phone number format."""
        phone = record.get('phone', '')
        if not phone:
            return record

        # Check if it looks like a valid Moroccan number
        digits = re.sub(r'[^\d]', '', phone)
        if len(digits) < 9 or len(digits) > 13:
            record['phone'] = ''
            self.stats['invalid_phones_fixed'] += 1

        return record

    def _validate_email(self, record: Dict) -> Dict:
        """Validate email format."""
        email = record.get('email', '')
        if not email:
            return record

        if not self.EMAIL_PATTERN.match(email):
            record['email'] = ''
            self.stats['invalid_emails_removed'] += 1
        elif any(bad in email.lower() for bad in ['example.com', 'test.com', 'sentry.io', 'wixpress', 'gstatic']):
            record['email'] = ''
            self.stats['invalid_emails_removed'] += 1

        return record

    def _validate_website(self, record: Dict) -> Dict:
        """Validate website URL format."""
        website = record.get('website', '')
        if not website:
            return record

        if not website.startswith(('http://', 'https://')):
            website = 'https://' + website
            record['website'] = website

        if not self.URL_PATTERN.match(website):
            record['website'] = ''

        return record

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL."""
        if not url or url in ['', 'n/a', 'none', 'None']:
            return ''

        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        return url

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ''

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove special characters at start/end
        text = text.strip('.,;:-_|/')

        return text

    def _remove_duplicates(self, data: List[Dict]) -> List[Dict]:
        """Remove duplicate businesses based on name and phone."""
        seen = set()
        unique = []

        for record in data:
            # Create a composite key from name + address + phone
            name_key = re.sub(r'\s+', '', record.get('name', '').lower())
            addr_key = re.sub(r'\s+', '', record.get('address', '').lower())
            phone_key = re.sub(r'[^\d]', '', record.get('phone', ''))

            # A lead is unique if it has a unique combination of name and location
            # If address is missing, we use phone, or just name
            key = f"{name_key}_{addr_key}_{phone_key}"

            if key not in seen:
                seen.add(key)
                unique.append(record)
            
        return unique

    def get_stats(self) -> Dict:
        """Return cleaning statistics."""
        return self.stats.copy()
