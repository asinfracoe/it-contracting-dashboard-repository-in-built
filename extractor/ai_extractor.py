# extractor/ai_extractor.py
# Fixed: LlamaCloud version argument
# Fixed: Record building from Groq output

import re
import json
import asyncio
import os
from groq import Groq
from config import (
    GROQ_API_KEY,
    LLAMA_API_KEY,
    LLAMA_TIER,
    KNOWN_VENDORS,
    KNOWN_SERVICES,
    MIN_VALID_PRICE,
    MAX_VALID_PRICE,
)

# Groq client
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# LlamaCloud client
llama = None
if LLAMA_API_KEY:
    try:
        from llama_parse import LlamaParse
        llama = LlamaParse(
            api_key=LLAMA_API_KEY,
            result_type="markdown",
            verbose=False,
        )
        print("  ✅ LlamaParse client initialised")
    except ImportError:
        print(
            "  ⚠️  llama-parse not installed — "
            "using pdfplumber only"
        )
    except Exception as e:
        print(f"  ⚠️  LlamaParse init error: {e}")

class AIExtractor:

    def __init__(self):
        self.stats = {
            "llama_success":  0,
            "llama_failed":   0,
            "groq_success":   0,
            "groq_failed":    0,
            "regex_fallback": 0,
        }

    # ══════════════════════════════════════
    #  LLAMACLOUD — PDF PARSING
    # ══════════════════════════════════════
    def parse_pdf_with_llama_sync(
        self, file_bytes, filename
    ):
        """
        Parse PDF with LlamaParse.
        Falls back gracefully if unavailable.
        """
        if not llama:
            return ""
    
        try:
            print(f"    📄 LlamaParse: {filename[:45]}...")
    
            import tempfile
            import os as _os
    
            with tempfile.NamedTemporaryFile(
                suffix='.pdf', delete=False
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
    
            try:
                documents = llama.load_data(tmp_path)
                if documents:
                    text = "\n\n".join(
                        doc.text for doc in documents
                        if doc.text
                    )
                    if text and len(text) > 100:
                        self.stats["llama_success"] += 1
                        print(
                            f"    ✅ LlamaParse: "
                            f"{len(text):,} chars"
                        )
                        return text
            finally:
                _os.unlink(tmp_path)
    
            self.stats["llama_failed"] += 1
            return ""
    
        except Exception as e:
            self.stats["llama_failed"] += 1
            print(f"    ⚠️  LlamaParse failed: {e}")
            return ""
    # ══════════════════════════════════════
    #  GROQ — AI EXTRACTION
    # ══════════════════════════════════════
    def extract_with_groq(self, text, filename, category):
        """
        Use Groq Llama 3.3 70B to extract
        structured per-license pricing data.
        """
        if not groq_client:
            print("    ⚠️  Groq not configured")
            return self._empty_result()

        # Truncate to fit context window
        text_truncated = text[:7000]

        vendor_hints  = ", ".join(KNOWN_VENDORS[:20])
        service_hints = ", ".join(KNOWN_SERVICES[:20])

        prompt = f"""You are an IT contract pricing analyst at PwC.
Extract ALL per-unit pricing from this vendor quote document.

Filename: {filename}
Category: {category}
Known Vendors: {vendor_hints}
Known Services: {service_hints}

DOCUMENT TEXT:
{text_truncated}

INSTRUCTIONS:
- Find EVERY product or service line with a price
- unit_price = price for ONE license, seat, or device
- If only total price exists, divide by quantity
- quantity = number of licenses or seats (default 1)
- Include ALL line items even if similar

Return ONLY this exact JSON structure, nothing else:
{{
  "vendor": "Company Name Here",
  "category": "{category}",
  "year": 2024,
  "quarter": "Q4",
  "currency": "USD",
  "confidence": "high",
  "line_items": [
    {{
      "service": "Exact Service Name",
      "unit_price": 33.80,
      "quantity": 654,
      "unit": "per license",
      "total_line_price": 22087.20,
      "description": "brief description"
    }}
  ]
}}

RULES:
- unit_price must be a positive number
- Do NOT include currency symbols in numbers
- Do NOT return empty line_items array
- Return ONLY the JSON object"""

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise IT contract pricing "
                            "analyst. Always return valid JSON only. "
                            "Never return empty line_items."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.05,
                max_tokens=2000,
            )

            raw = response.choices[0].message.content.strip()
            print(f"    🔍 Groq raw response length: {len(raw)} chars")

            result = self._parse_json_response(raw)

            if result and result.get("line_items"):
                count = len(result["line_items"])
                self.stats["groq_success"] += 1
                print(f"    ✅ Groq: {count} items")
                return result

            print(f"    ⚠️  Groq returned no line_items")
            self.stats["groq_failed"] += 1
            return self._empty_result()

        except Exception as e:
            self.stats["groq_failed"] += 1
            print(f"    ⚠️  Groq error: {e}")
            return self._empty_result()

    # ══════════════════════════════════════
    #  JSON PARSER
    # ══════════════════════════════════════
    def _parse_json_response(self, raw_text):
        """
        Robustly parse JSON from AI response.
        Handles markdown code blocks and
        common formatting issues.
        """
        if not raw_text:
            return None

        # Remove markdown code blocks
        text = raw_text
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find JSON object in text
        start = text.find('{')
        end   = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        # Fix common JSON issues
        try:
            fixed = re.sub(r',\s*}', '}', text)
            fixed = re.sub(r',\s*]', ']', fixed)
            fixed = re.sub(r'[\x00-\x1f\x7f]', '', fixed)
            start = fixed.find('{')
            end   = fixed.rfind('}')
            if start != -1 and end != -1:
                return json.loads(fixed[start:end+1])
        except json.JSONDecodeError:
            pass

        return None

    def _empty_result(self):
        return {
            "vendor":     "Unknown",
            "category":   "",
            "year":       2024,
            "quarter":    "Q1",
            "currency":   "USD",
            "confidence": "low",
            "line_items": [],
        }

    # ══════════════════════════════════════
    #  REGEX FALLBACKS
    # ══════════════════════════════════════
    def extract_price_regex(self, text):
        """Extract prices using regex patterns."""
        prices = []
        patterns = [
            r'\$\s*([\d,]+(?:\.\d{1,2})?)',
            r'USD\s*([\d,]+(?:\.\d{1,2})?)',
            r'(?:price|cost|amount|total)[:\s]*'
            r'\$?\s*([\d,]+(?:\.\d{1,2})?)',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    n = float(m.group(1).replace(',', ''))
                    if MIN_VALID_PRICE <= n <= MAX_VALID_PRICE:
                        prices.append(n)
                except (ValueError, IndexError):
                    continue

        if prices:
            self.stats["regex_fallback"] += 1
            prices.sort()
            return prices[0]
        return 0

    def extract_vendor_regex(self, text, filename):
        """Match vendor names from known list."""
        text_lower  = text.lower()
        fname_lower = filename.lower()
        for vendor in KNOWN_VENDORS:
            vl = vendor.lower()
            if vl in text_lower or vl in fname_lower:
                return vendor
        return "Unknown"

    def extract_services_regex(self, text):
        """Match service names from known list."""
        found   = []
        t_lower = text.lower()
        for service in KNOWN_SERVICES:
            if service.lower() in t_lower:
                found.append(service)
        return list(set(found))

    def extract_year_regex(self, text, filename):
        years = re.findall(
            r'\b(202[0-9])\b', text + " " + filename
        )
        return int(max(years)) if years else 2024

    def extract_quarter_regex(self, text):
        months = re.findall(
            r'\b(jan|feb|mar|apr|may|jun|'
            r'jul|aug|sep|oct|nov|dec)\w*\b',
            text.lower()
        )
        qmap = {
            "jan": "Q1", "feb": "Q1", "mar": "Q1",
            "apr": "Q2", "may": "Q2", "jun": "Q2",
            "jul": "Q3", "aug": "Q3", "sep": "Q3",
            "oct": "Q4", "nov": "Q4", "dec": "Q4",
        }
        return qmap.get(months[0], "Q1") if months else "Q1"

    # ══════════════════════════════════════
    #  MASTER EXTRACTION
    # ══════════════════════════════════════
    async def extract_full(
        self,
        file_bytes,
        filename,
        category,
        text_from_processor=None
    ):
        """
        Full pipeline:
        LlamaCloud → Groq → Regex fallback
        Returns list of validated price records.
        """
        from pathlib import Path
        print(f"\n  🔍 Extracting: {filename}")

        text = ""

        # Step 1 — LlamaCloud for PDFs
        if Path(filename).suffix.lower() == ".pdf":
            llama_text = await asyncio.get_event_loop().run_in_executor(
                None,
                self.parse_pdf_with_llama_sync,
                file_bytes,
                filename
            )
            if llama_text and len(llama_text) > 100:
                text = llama_text
                print(
                    f"    ✅ Using LlamaCloud text: "
                    f"{len(text):,} chars"
                )

        # Step 2 — Fall back to file processor text
        if not text and text_from_processor:
            text = text_from_processor
            print(
                f"    ℹ️  Using file processor text: "
                f"{len(text):,} chars"
            )

        if not text:
            print(f"    ❌ No text available for {filename}")
            return []

        # Step 3 — Groq AI extraction
        extracted  = self.extract_with_groq(text, filename, category)
        line_items = extracted.get("line_items", [])
        vendor     = extracted.get("vendor", "Unknown")
        cat        = extracted.get("category", "") or category
        year       = extracted.get("year", 0)
        quarter    = extracted.get("quarter", "Q1")
        currency   = extracted.get("currency", "USD")
        confidence = extracted.get("confidence", "medium")

        # Step 4 — Fill gaps with regex
        if not vendor or vendor == "Unknown":
            vendor = self.extract_vendor_regex(text, filename)
        if not year or year < 2018:
            year = self.extract_year_regex(text, filename)
        if not quarter:
            quarter = self.extract_quarter_regex(text)
        if not cat:
            cat = category

        # Step 5 — Regex fallback if Groq found nothing
        if not line_items:
            print(f"    ⚠️  No AI line items — trying regex")
            price    = self.extract_price_regex(text)
            services = self.extract_services_regex(text)
            if price > 0:
                if services:
                    for svc in services[:5]:
                        line_items.append({
                            "service":          svc,
                            "unit_price":       round(price, 2),
                            "quantity":         1,
                            "unit":             "per quote",
                            "total_line_price": price,
                            "description":      "regex extracted",
                        })
                else:
                    line_items.append({
                        "service":          filename,
                        "unit_price":       round(price, 2),
                        "quantity":         1,
                        "unit":             "per quote",
                        "total_line_price": price,
                        "description":      "regex extracted",
                    })

        if not line_items:
            print(f"    ❌ No items found after all methods")
            return []

        # Step 6 — Build and validate records
        records = []
        for item in line_items:
            # Parse unit price robustly
            raw_price = item.get("unit_price", 0)
            try:
                unit_price = float(
                    str(raw_price)
                    .replace(',', '')
                    .replace('$', '')
                    .strip()
                )
            except (ValueError, TypeError):
                unit_price = 0

            # Skip zero or negative prices
            if unit_price <= 0:
                print(
                    f"    ⚠️  Skipping zero price: "
                    f"{item.get('service','?')}"
                )
                continue

            # Parse quantity
            try:
                quantity = int(
                    float(str(item.get("quantity", 1)))
                )
                if quantity <= 0:
                    quantity = 1
            except (ValueError, TypeError):
                quantity = 1

            # Parse total line price
            try:
                total = float(
                    str(item.get("total_line_price", 0))
                    .replace(',', '')
                    .replace('$', '')
                )
            except (ValueError, TypeError):
                total = round(unit_price * quantity, 2)

            service = str(
                item.get("service", "Unknown Service")
            ).strip()
            if not service:
                service = filename

            unit = str(
                item.get("unit", "per license")
            ).strip() or "per license"

            record = {
                "cat":              cat,
                "vendor":           vendor,
                "file":             filename,
                "service":          service,
                "unit_price":       round(unit_price, 2),
                "quantity":         quantity,
                "unit":             unit,
                "total_line_price": round(total, 2),
                "description":      str(
                    item.get("description", "")
                ).strip(),
                "year":             year,
                "quarter":          quarter,
                "currency":         currency,
                "confidence":       confidence,
                "source":           "github",
            }
            records.append(record)
            print(
                f"    ✅ {vendor[:15]:<15} | "
                f"{service[:28]:<28} | "
                f"${unit_price:>10.2f}"
            )

        print(f"    📦 {len(records)} records built from {filename}")
        return records

    def get_stats(self):
        return self.stats
