# extractor/catalog_builder.py

import json
import os
import re
from datetime import datetime
from config import (
    KNOWN_VENDORS,
    KNOWN_SERVICES,
    MIN_VALID_PRICE,
    MAX_VALID_PRICE,
    OUTPUT_FILE,
    ERROR_LOG_FILE,
    PROGRESS_FILE,
)


class CatalogBuilder:

    def __init__(self):
        self.errors   = []
        self.warnings = []
        self.stats    = {
            "total_input":     0,
            "total_output":    0,
            "duplicates":      0,
            "invalid_price":   0,
            "invalid_vendor":  0,
            "invalid_service": 0,
        }

    # ══════════════════════════════════════
    #  MAIN BUILD METHOD
    # ══════════════════════════════════════
    def build(self, records: list) -> list:
        """
        Take raw extracted records from all
        files, clean and validate each one,
        remove duplicates, and return the
        final sorted catalog list ready to
        be saved as catalog_data.json.
        """
        if not records:
            print("  ⚠️  CatalogBuilder received 0 records")
            return []

        self.stats["total_input"] = len(records)
        print(f"  📦 CatalogBuilder: processing {len(records)} raw records")

        cleaned = []
        seen    = set()

        for i, r in enumerate(records):
            try:
                cleaned_record = self._clean_record(r)

                if cleaned_record is None:
                    continue

                # Deduplication key
                dedup_key = (
                    str(cleaned_record.get("vendor",  "")).lower().strip(),
                    str(cleaned_record.get("service", "")).lower().strip(),
                    str(cleaned_record.get("unit_price", 0)),
                    str(cleaned_record.get("file",    "")).lower().strip(),
                )

                if dedup_key in seen:
                    self.stats["duplicates"] += 1
                    continue

                seen.add(dedup_key)
                cleaned.append(cleaned_record)

            except Exception as e:
                self.errors.append({
                    "index":  i,
                    "error":  str(e),
                    "record": str(r)[:200],
                })
                self.warnings.append(f"Record {i} skipped: {e}")
                continue

        # Sort by category → vendor → service
        cleaned.sort(key=lambda r: (
            str(r.get("cat",     "")),
            str(r.get("vendor",  "")),
            str(r.get("service", "")),
        ))

        self.stats["total_output"] = len(cleaned)

        print(f"  ✅ CatalogBuilder: {len(cleaned)} valid records")
        print(f"     Input:      {self.stats['total_input']}")
        print(f"     Output:     {self.stats['total_output']}")
        print(f"     Duplicates: {self.stats['duplicates']}")
        print(f"     Bad price:  {self.stats['invalid_price']}")

        if self.warnings:
            print(f"     Warnings:   {len(self.warnings)}")

        return cleaned

    # ══════════════════════════════════════
    #  RECORD CLEANER
    # ══════════════════════════════════════
    def _clean_record(self, r: dict):
        """
        Validate and clean a single raw record.
        Returns a clean dict or None if the
        record should be discarded entirely.
        """
        if not isinstance(r, dict):
            self.stats["invalid_price"] += 1
            return None

        # ── Unit Price ──────────────────────
        unit_price = self._parse_price(r)
        if unit_price is None:
            self.stats["invalid_price"] += 1
            return None

        # ── Vendor ──────────────────────────
        vendor = self._parse_vendor(r)

        # ── Service ─────────────────────────
        service = self._parse_service(r)

        # ── Category ────────────────────────
        cat = self._parse_category(r)

        # ── Quantity ────────────────────────
        quantity = self._parse_quantity(r)

        # ── Total Line Price ─────────────────
        total = self._parse_total(r, unit_price, quantity)

        # ── Year ────────────────────────────
        year = self._parse_year(r)

        # ── Quarter ─────────────────────────
        quarter = self._parse_quarter(r)

        # ── Currency ────────────────────────
        currency = self._parse_currency(r)

        # ── Confidence ──────────────────────
        confidence = self._parse_confidence(r)

        # ── Unit ────────────────────────────
        unit = self._parse_unit(r)

        # ── File ────────────────────────────
        file_name = str(r.get("file", "")).strip()

        # ── Description ─────────────────────
        description = str(r.get("description", "")).strip()

        # ── Source ──────────────────────────
        source = str(r.get("source", "github")).strip()

        return {
            "cat":              cat,
            "vendor":           vendor,
            "file":             file_name,
            "service":          service,
            "unit_price":       round(unit_price, 2),
            "quantity":         quantity,
            "unit":             unit,
            "total_line_price": round(total, 2),
            "description":      description,
            "year":             year,
            "quarter":          quarter,
            "currency":         currency,
            "confidence":       confidence,
            "source":           source,
        }

    # ══════════════════════════════════════
    #  FIELD PARSERS
    # ══════════════════════════════════════
    def _parse_price(self, r: dict):
        """
        Parse unit price from multiple possible
        field names. Returns float or None.
        Accepts any positive value above
        MIN_VALID_PRICE.
        """
        # Try multiple field name variations
        candidates = [
            "unit_price",
            "price",
            "unit price",
            "unitprice",
            "unit_cost",
            "per_unit",
        ]

        for key in candidates:
            val = r.get(key)
            if val is None:
                continue

            parsed = self._to_float(val)
            if parsed is not None and parsed > 0:
                if parsed < MIN_VALID_PRICE:
                    # Price exists but below minimum
                    # Still include it — may be valid
                    # unit price like $0.50
                    return round(parsed, 4)
                if parsed > MAX_VALID_PRICE:
                    self.stats["invalid_price"] += 1
                    return None
                return round(parsed, 4)

        # No valid price found
        return None

    def _parse_vendor(self, r: dict) -> str:
        """Parse and clean vendor name."""
        vendor = str(r.get("vendor", "")).strip()

        # Remove common noise
        for noise in ["Unknown", "N/A", "None", "null", ""]:
            if vendor.lower() == noise.lower():
                vendor = ""
                break

        if not vendor:
            self.stats["invalid_vendor"] += 1
            # Try to get from filename
            file_name = str(r.get("file", ""))
            if file_name:
                # Use first part of filename as vendor hint
                vendor = file_name.split("_")[0].split("-")[0].strip()
            if not vendor:
                vendor = "Unknown Vendor"

        return vendor

    def _parse_service(self, r: dict) -> str:
        """Parse and clean service name."""
        # Try multiple field name variations
        service = ""
        for key in ["service", "service_name", "product",
                    "product_name", "description", "item"]:
            val = str(r.get(key, "")).strip()
            if val and val.lower() not in [
                "unknown", "none", "null", "n/a", ""
            ]:
                service = val
                break

        if not service:
            self.stats["invalid_service"] += 1
            # Fall back to file name
            file_name = str(r.get("file", "Unknown Service"))
            service = file_name if file_name else "Unknown Service"

        # Truncate if too long
        if len(service) > 200:
            service = service[:200].strip()

        return service

    def _parse_category(self, r: dict) -> str:
        """Parse category from record."""
        cat = str(r.get("cat", "")).strip()
        if not cat or cat.lower() in ["unknown", "none", "null"]:
            cat = str(r.get("category", "")).strip()
        if not cat:
            cat = "Uncategorised"
        return cat

    def _parse_quantity(self, r: dict) -> int:
        """Parse quantity — defaults to 1."""
        try:
            qty = int(float(str(
                r.get("quantity", 1) or 1
            )))
            return max(1, qty)
        except (ValueError, TypeError):
            return 1

    def _parse_total(
        self, r: dict, unit_price: float, quantity: int
    ) -> float:
        """
        Parse total line price.
        Falls back to unit_price × quantity.
        """
        for key in ["total_line_price", "total", "extended_price",
                    "line_total", "total_price"]:
            val = r.get(key)
            if val is None:
                continue
            parsed = self._to_float(val)
            if parsed is not None and parsed > 0:
                return round(parsed, 2)

        return round(unit_price * quantity, 2)

    def _parse_year(self, r: dict) -> int:
        """Parse year — defaults to current year."""
        try:
            year = int(float(str(r.get("year", 0) or 0)))
            if 2018 <= year <= 2035:
                return year
        except (ValueError, TypeError):
            pass
        return datetime.now().year

    def _parse_quarter(self, r: dict) -> str:
        """Parse quarter — defaults to Q1."""
        quarter = str(r.get("quarter", "Q1")).strip().upper()
        if quarter in ["Q1", "Q2", "Q3", "Q4"]:
            return quarter

        # Try to extract Q from string like "Q2 2024"
        match = re.search(r'Q([1-4])', quarter, re.IGNORECASE)
        if match:
            return f"Q{match.group(1)}"

        return "Q1"

    def _parse_currency(self, r: dict) -> str:
        """Parse currency — defaults to USD."""
        currency = str(
            r.get("currency", "USD") or "USD"
        ).strip().upper()

        valid = ["USD", "GBP", "EUR", "AUD", "CAD", "JPY",
                 "INR", "SGD", "HKD", "CHF"]
        if currency in valid:
            return currency

        # Try extracting 3-letter code
        match = re.search(r'\b([A-Z]{3})\b', currency)
        if match and match.group(1) in valid:
            return match.group(1)

        return "USD"

    def _parse_confidence(self, r: dict) -> str:
        """Parse confidence level."""
        confidence = str(
            r.get("confidence", "medium") or "medium"
        ).strip().lower()

        if confidence in ["high", "medium", "low"]:
            return confidence
        return "medium"

    def _parse_unit(self, r: dict) -> str:
        """Parse unit type."""
        unit = str(
            r.get("unit", "per license") or "per license"
        ).strip()

        if not unit or unit.lower() in ["none", "null", "n/a"]:
            return "per license"

        # Normalise common variations
        unit_lower = unit.lower()
        if any(x in unit_lower for x in [
            "license", "licence", "lic"
        ]):
            return "per license"
        if any(x in unit_lower for x in ["seat", "user"]):
            return "per seat"
        if "device" in unit_lower:
            return "per device"
        if "month" in unit_lower:
            return "per month"
        if "year" in unit_lower or "annual" in unit_lower:
            return "per year"
        if "quote" in unit_lower:
            return "per quote"

        return unit

    # ══════════════════════════════════════
    #  UTILITY
    # ══════════════════════════════════════
    def _to_float(self, val) -> float:
        """
        Safely convert any value to float.
        Handles strings with $, commas etc.
        Returns None if conversion fails.
        """
        if val is None:
            return None

        if isinstance(val, (int, float)):
            f = float(val)
            return f if f >= 0 else None

        if isinstance(val, str):
            # Remove currency symbols and whitespace
            cleaned = (
                val
                .replace('$', '')
                .replace('£', '')
                .replace('€', '')
                .replace(',', '')
                .replace(' ', '')
                .strip()
            )
            if not cleaned:
                return None
            try:
                f = float(cleaned)
                return f if f >= 0 else None
            except ValueError:
                return None

        return None

    # ══════════════════════════════════════
    #  SAVE AND REPORT
    # ══════════════════════════════════════
    def save_catalog(self, catalog: list, output_path: str):
        """Save catalog list to JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        size_kb = os.path.getsize(output_path) / 1024
        print(f"  💾 Saved {len(catalog)} records to {output_path}")
        print(f"     File size: {size_kb:.1f} KB")

    def save_errors(self, output_dir: str):
        """Save error log if there were any errors."""
        if not self.errors:
            return
        error_path = os.path.join(output_dir, ERROR_LOG_FILE)
        try:
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "total_errors": len(self.errors),
                    "errors": self.errors,
                }, f, indent=2)
            print(f"  📋 Error log saved: {error_path}")
        except Exception as e:
            print(f"  ⚠️  Could not save error log: {e}")

    def save_progress(self, progress: dict, output_dir: str):
        """Save extraction progress to JSON file."""
        progress_path = os.path.join(output_dir, PROGRESS_FILE)
        try:
            with open(progress_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    **progress,
                    "stats": self.stats,
                }, f, indent=2)
        except Exception as e:
            print(f"  ⚠️  Could not save progress: {e}")

    def get_summary(self, catalog: list) -> dict:
        """
        Return a summary dict of the catalog
        for logging and reporting purposes.
        """
        if not catalog:
            return {"total": 0}

        vendors    = list(set(r.get("vendor", "")
                              for r in catalog))
        categories = list(set(r.get("cat", "")
                               for r in catalog))
        services   = list(set(r.get("service", "")
                               for r in catalog))

        prices = [
            r.get("unit_price", 0)
            for r in catalog
            if r.get("unit_price", 0) > 0
        ]

        avg_price = (
            sum(prices) / len(prices) if prices else 0
        )
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        return {
            "total_records": len(catalog),
            "vendors":       len(vendors),
            "categories":    len(categories),
            "services":      len(services),
            "avg_unit_price": round(avg_price, 2),
            "min_unit_price": round(min_price, 2),
            "max_unit_price": round(max_price, 2),
            "vendor_list":    sorted(vendors),
            "category_list":  sorted(categories),
        }

    def print_summary(self, catalog: list):
        """Print a readable summary to console."""
        summary = self.get_summary(catalog)

        print(f"\n{'═' * 50}")
        print(f"  CATALOG SUMMARY")
        print(f"{'─' * 50}")
        print(f"  Total records:  {summary['total_records']}")
        print(f"  Vendors:        {summary['vendors']}")
        print(f"  Categories:     {summary['categories']}")
        print(f"  Services:       {summary['services']}")
        print(f"  Avg unit price: ${summary['avg_unit_price']:,.2f}")
        print(f"  Min unit price: ${summary['min_unit_price']:,.2f}")
        print(f"  Max unit price: ${summary['max_unit_price']:,.2f}")

        if summary.get("category_list"):
            print(f"\n  Categories:")
            for cat in summary["category_list"]:
                count = sum(
                    1 for r in catalog
                    if r.get("cat") == cat
                )
                print(f"    {cat:<35} {count:>4} records")

        if summary.get("vendor_list"):
            print(f"\n  Top Vendors:")
            vendor_counts = {}
            for r in catalog:
                v = r.get("vendor", "")
                vendor_counts[v] = vendor_counts.get(v, 0) + 1
            top = sorted(
                vendor_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            for vendor, count in top:
                print(f"    {vendor:<35} {count:>4} records")

        print(f"{'═' * 50}\n")
