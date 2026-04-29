# extractor/catalog_builder.py

import json
import os
from datetime import datetime
from config import (
    KNOWN_VENDORS,
    KNOWN_SERVICES,
    MIN_VALID_PRICE,
    MAX_VALID_PRICE,
)


class CatalogBuilder:

    def build(self, records: list) -> list:
        """
        Take raw extracted records, clean and
        validate them, and return a final catalog
        list ready to save as JSON.
        """
        if not records:
            return []

        cleaned = []
        seen = set()

        for r in records:
            try:
                cleaned_record = self._clean(r)
                if cleaned_record is None:
                    continue

                # Simple deduplication by key fields
                key = (
                    str(cleaned_record.get('vendor', '')).lower(),
                    str(cleaned_record.get('service', '')).lower(),
                    str(cleaned_record.get('unit_price', 0)),
                    str(cleaned_record.get('file', '')).lower(),
                )
                if key in seen:
                    continue
                seen.add(key)

                cleaned.append(cleaned_record)

            except Exception as e:
                print(f"    ⚠️  CatalogBuilder skip: {e}")
                continue

        # Sort by category then vendor
        cleaned.sort(key=lambda r: (
            r.get('cat', ''),
            r.get('vendor', ''),
            r.get('service', ''),
        ))

        print(f"  📦 CatalogBuilder: {len(cleaned)} valid records")
        return cleaned

    def _clean(self, r: dict) -> dict:
        """
        Validate and clean a single record.
        Returns None if the record should be
        discarded.
        """
        if not isinstance(r, dict):
            return None

        # Unit price must exist and be positive
        unit_price = 0
        for key in ['unit_price', 'price', 'unit price']:
            val = r.get(key, 0)
            try:
                unit_price = float(str(val).replace(',', '').replace('$', ''))
            except (ValueError, TypeError):
                unit_price = 0
            if unit_price > 0:
                break

        if unit_price <= 0:
            return None

        if unit_price < MIN_VALID_PRICE:
            return None

        if unit_price > MAX_VALID_PRICE:
            return None

        # Vendor must exist
        vendor = str(r.get('vendor', '')).strip()
        if not vendor or vendor.lower() in ['unknown', 'none', '']:
            vendor = 'Unknown Vendor'

        # Service must exist
        service = str(r.get('service', '')).strip()
        if not service or service.lower() in ['unknown', 'none', '']:
            service = str(r.get('file', 'Unknown Service'))

        # Category
        cat = str(r.get('cat', '')).strip()
        if not cat:
            cat = 'Uncategorised'

        # Quantity
        try:
            quantity = int(float(str(r.get('quantity', 1))))
            if quantity <= 0:
                quantity = 1
        except (ValueError, TypeError):
            quantity = 1

        # Total line price
        try:
            total = float(str(
                r.get('total_line_price', 0)
            ).replace(',', '').replace('$', ''))
        except (ValueError, TypeError):
            total = round(unit_price * quantity, 2)

        # Year
        try:
            year = int(r.get('year', datetime.now().year))
            if year < 2018 or year > 2030:
                year = datetime.now().year
        except (ValueError, TypeError):
            year = datetime.now().year

        # Quarter
        quarter = str(r.get('quarter', 'Q1')).strip()
        if quarter not in ['Q1', 'Q2', 'Q3', 'Q4']:
            quarter = 'Q1'

        # Currency
        currency = str(r.get('currency', 'USD')).strip().upper()
        if currency not in ['USD', 'GBP', 'EUR', 'AUD', 'CAD']:
            currency = 'USD'

        # Confidence
        confidence = str(r.get('confidence', 'medium')).lower()
        if confidence not in ['high', 'medium', 'low']:
            confidence = 'medium'

        return {
            'cat':              cat,
            'vendor':           vendor,
            'file':             str(r.get('file', '')),
            'service':          service,
            'unit_price':       round(unit_price, 2),
            'quantity':         quantity,
            'unit':             str(r.get('unit', 'per license')).strip(),
            'total_line_price': round(total, 2),
            'description':      str(r.get('description', '')).strip(),
            'year':             year,
            'quarter':          quarter,
            'currency':         currency,
            'confidence':       confidence,
            'source':           'github',
        }
