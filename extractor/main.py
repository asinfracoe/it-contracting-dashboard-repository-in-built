# extractor/main.py
# Reads quote files from quotes/ folder in GitHub repository
# No SharePoint connection needed

import os
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_extractor import AIExtractor
from file_processor import FileProcessor
from catalog_builder import CatalogBuilder
from github_pusher import GitHubPusher
from config import (
    FOLDER_TO_CATEGORY,
    SUPPORTED_EXTENSIONS,
    OUTPUT_FILE,
    DELAY_BETWEEN_FILES,
)


def find_quotes_folder():
    """
    Find the quotes/ folder relative to
    where main.py is running from.
    Handles both local runs and GitHub Actions.
    """
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    candidates = [
        script_dir.parent / 'quotes',
        script_dir / 'quotes',
        Path('quotes'),
        Path('../quotes'),
    ]

    for p in candidates:
        resolved = p.resolve()
        if resolved.exists() and resolved.is_dir():
            print(f"  ✅ quotes folder found: {resolved}")
            return resolved

    print("  ❌ quotes/ folder not found")
    print("     Searched in:")
    for p in candidates:
        print(f"       {p.resolve()}")
    return None


def get_files_in_folder(folder_path: Path):
    """
    Get all supported files directly inside
    a folder and one level of subfolders.
    Skips hidden files and .gitkeep files.
    """
    files = []

    for item in folder_path.rglob('*'):
        if not item.is_file():
            continue
        if item.name.startswith('.'):
            continue
        if item.name == '.gitkeep':
            continue
        if item.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        files.append(item)

    return files


async def process_file(
    file_path: Path,
    category: str,
    extractor: AIExtractor,
    processor: FileProcessor
):
    """
    Process a single vendor quote file.
    Returns list of extracted price records.
    """
    filename = file_path.name
    ext = file_path.suffix.lower()
    size_kb = file_path.stat().st_size / 1024

    print(f"\n  📄 {filename}")
    print(f"     Size: {size_kb:.1f} KB  |  Category: {category}")

    try:
        file_bytes = file_path.read_bytes()

        # Extract text using file processor
        text_from_processor = ""
        try:
            if ext in ['.xlsx', '.xls']:
                text_from_processor = processor.process_excel(
                    file_bytes, filename
                )
                print(f"     📊 Excel processed")

            elif ext == '.csv':
                text_from_processor = file_bytes.decode(
                    'utf-8', errors='replace'
                )
                print(f"     📊 CSV processed")

            elif ext in ['.docx', '.doc']:
                text_from_processor = processor.process_word(
                    file_bytes, filename
                )
                print(f"     📝 Word processed")

            elif ext == '.txt':
                text_from_processor = file_bytes.decode(
                    'utf-8', errors='replace'
                )
                print(f"     📝 Text processed")

            elif ext == '.pdf':
                text_from_processor = processor.process_pdf(
                    file_bytes, filename
                )
                print(f"     📑 PDF pre-processed")

        except Exception as e:
            print(f"     ⚠️  File processor error: {e}")

        # Run AI extraction pipeline
        records = await extractor.extract_full(
            file_bytes=file_bytes,
            filename=filename,
            category=category,
            text_from_processor=text_from_processor
        )

        if records:
            print(f"     ✅ {len(records)} records extracted")
            for r in records[:2]:
                print(
                    f"        → {r.get('vendor','?')} | "
                    f"{str(r.get('service','?'))[:30]} | "
                    f"${r.get('unit_price',0):.2f}"
                )
        else:
            print(f"     ⚠️  No records extracted from this file")

        return records

    except MemoryError:
        print(f"     ❌ File too large to process: {filename}")
        return []
    except Exception as e:
        print(f"     ❌ Failed: {e}")
        return []


async def main():
    print("=" * 60)
    print("  IT CONTRACTING DASHBOARD — EXTRACTOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    # Locate quotes folder
    print("\n📁 Locating quotes folder...")
    quotes_root = find_quotes_folder()

    if not quotes_root:
        print("\n❌ Cannot find quotes/ folder.")
        print("   Create a quotes/ folder in the repo root")
        print("   with category subfolders and upload files.")
        sys.exit(1)

    # Scan category folders
    print("\n📂 Scanning category folders...")
    folder_queue = []

    for folder_name, category in FOLDER_TO_CATEGORY.items():
        folder_path = quotes_root / folder_name

        if not folder_path.exists():
            print(f"  ⚠️  Not found: {folder_name}")
            continue

        files = get_files_in_folder(folder_path)

        if not files:
            print(f"  ℹ️  Empty: {folder_name}")
            continue

        folder_queue.append({
            'name':     folder_name,
            'path':     folder_path,
            'category': category,
            'files':    files,
        })
        print(f"  ✅ {folder_name}: {len(files)} files")

    total_files = sum(len(f['files']) for f in folder_queue)
    print(f"\n  Total files to process: {total_files}")

    if total_files == 0:
        print("\n⚠️  No files found in quotes/ subfolders.")
        print("   Upload PDF or Excel files to the category folders.")
        sys.exit(0)

    # Initialise components
    extractor = AIExtractor()
    processor = FileProcessor()
    builder   = CatalogBuilder()

    # Process all files
    all_records  = []
    files_ok     = 0
    files_failed = 0

    for folder_info in folder_queue:
        cat = folder_info['category']
        print(f"\n{'─' * 50}")
        print(f"  📂 {cat}  ({len(folder_info['files'])} files)")
        print('─' * 50)

        for file_path in folder_info['files']:
            try:
                records = await process_file(
                    file_path=file_path,
                    category=cat,
                    extractor=extractor,
                    processor=processor,
                )

                if records:
                    all_records.extend(records)
                    files_ok += 1
                else:
                    files_failed += 1

            except Exception as e:
                print(f"  ❌ Unexpected error on {file_path.name}: {e}")
                files_failed += 1

            await asyncio.sleep(DELAY_BETWEEN_FILES)

    # Build and save catalog
    print(f"\n{'=' * 60}")
    print("  📦 BUILDING CATALOG")
    print('=' * 60)

    catalog = builder.build(all_records)

    print(f"  Records built:     {len(catalog)}")
    print(f"  Files successful:  {files_ok}")
    print(f"  Files failed:      {files_failed}")

    if not catalog:
        print("\n⚠️  Catalog is empty — nothing to save.")
        print("   Check your files contain visible pricing tables.")
        sys.exit(0)

    # Save catalog_data.json to repo root
    repo_root   = quotes_root.parent
    output_path = repo_root / OUTPUT_FILE

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    file_size = output_path.stat().st_size / 1024
    print(f"\n  💾 Saved: {output_path}")
    print(f"     {len(catalog)} records  |  {file_size:.1f} KB")

    # Show sample records
    if catalog:
        print("\n  📋 Sample records:")
        for r in catalog[:5]:
            print(
                f"     {r.get('vendor','?')[:18]:<18} | "
                f"{str(r.get('service','?'))[:28]:<28} | "
                f"${r.get('unit_price',0):>10.2f}"
            )

    # Push to GitHub
    print(f"\n{'=' * 60}")
    print("  📤 PUSHING TO GITHUB")
    print('=' * 60)

    try:
        pusher = GitHubPusher()
        pusher.push_catalog(str(output_path), OUTPUT_FILE)
        print("  ✅ catalog_data.json pushed successfully")
    except Exception as e:
        print(f"  ⚠️  Push error: {e}")
        print("  catalog_data.json saved locally — push manually")

    # AI stats
    stats = extractor.get_stats()
    print(f"\n{'=' * 60}")
    print("  ✅ EXTRACTION COMPLETE")
    print('─' * 60)
    print(f"  Total records:    {len(catalog)}")
    print(
        f"  Unique vendors:   "
        f"{len(set(r.get('vendor','') for r in catalog))}"
    )
    print(
        f"  Categories used:  "
        f"{len(set(r.get('cat','') for r in catalog))}"
    )
    print(f"  LlamaCloud OK:    {stats.get('llama_success', 0)}")
    print(f"  Groq OK:          {stats.get('groq_success', 0)}")
    print(f"  Regex fallback:   {stats.get('regex_fallback', 0)}")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
