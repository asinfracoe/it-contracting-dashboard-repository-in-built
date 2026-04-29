# extractor/file_processor.py

import io
from config import SUPPORTED_EXTENSIONS


class FileProcessor:

    def process_pdf(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text from PDF using available
        libraries. Tries pdfplumber first then
        falls back to pypdf.
        """
        text = ""

        # Try pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                parts = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    parts.append(page_text)

                    # Extract tables
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            if row:
                                row_text = " | ".join(
                                    str(cell or "")
                                    for cell in row
                                )
                                parts.append(row_text)

                text = "\n".join(parts)
                if text and len(text) > 50:
                    print(f"     📑 pdfplumber: {len(text):,} chars")
                    return text
        except Exception as e:
            print(f"     ⚠️  pdfplumber failed: {e}")

        # Try pypdf as fallback
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            parts = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                parts.append(page_text)
            text = "\n".join(parts)
            if text:
                print(f"     📑 pypdf: {len(text):,} chars")
                return text
        except Exception as e:
            print(f"     ⚠️  pypdf failed: {e}")

        return text

    def process_excel(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text from Excel files.
        Reads all sheets and converts to
        readable text format.
        """
        try:
            import pandas as pd

            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            parts = []

            for sheet_name in xl.sheet_names:
                try:
                    df = xl.parse(sheet_name)
                    if df.empty:
                        continue

                    # Clean dataframe
                    df = df.dropna(how='all')
                    df = df.fillna('')

                    parts.append(f"Sheet: {sheet_name}")
                    parts.append(
                        df.to_string(index=False, max_rows=200)
                    )

                except Exception as e:
                    print(
                        f"     ⚠️  Sheet {sheet_name} error: {e}"
                    )
                    continue

            text = "\n\n".join(parts)
            if text:
                print(f"     📊 Excel: {len(text):,} chars")
            return text

        except Exception as e:
            print(f"     ❌ Excel processing failed: {e}")
            return ""

    def process_word(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text from Word documents.
        """
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            parts = []

            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text.strip())

            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(
                        cell.text.strip()
                        for cell in row.cells
                        if cell.text.strip()
                    )
                    if row_text:
                        parts.append(row_text)

            text = "\n".join(parts)
            if text:
                print(f"     📝 Word: {len(text):,} chars")
            return text

        except Exception as e:
            print(f"     ❌ Word processing failed: {e}")
            return ""

    def process_csv(self, file_bytes: bytes, filename: str) -> str:
        """
        Read CSV file as plain text.
        """
        try:
            text = file_bytes.decode('utf-8', errors='replace')
            print(f"     📊 CSV: {len(text):,} chars")
            return text
        except Exception as e:
            print(f"     ❌ CSV processing failed: {e}")
            return ""
