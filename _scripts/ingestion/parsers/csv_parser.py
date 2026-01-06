"""
CSV file parser (.csv).

Extracts tabular data from CSV files for analysis.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3
"""

import csv
from pathlib import Path
from typing import List

from .base import BaseParser
from ..types import ParsedContent


class CSVParser(BaseParser):
    """
    Parse CSV files.

    Extracts:
    - Row data as text
    - Column headers
    - Structured table data
    """

    def get_extensions(self) -> List[str]:
        return [".csv"]

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() == ".csv"

    def get_file_type(self) -> str:
        return "csv"

    def parse(self, path: Path) -> ParsedContent:
        """Parse CSV file and extract text content."""
        all_text = []
        rows_data = []
        headers = []
        total_rows = 0

        # Try different encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        content = None

        for encoding in encodings:
            try:
                with open(path, 'r', encoding=encoding, newline='') as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return ParsedContent(
                text="[Error: Could not decode CSV file with any supported encoding]",
                title=path.stem,
                metadata={"error": "encoding error"}
            )

        try:
            # Detect delimiter
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(content[:4096])
            except csv.Error:
                # Default to comma
                dialect = csv.excel

            reader = csv.reader(content.splitlines(), dialect)

            for i, row in enumerate(reader):
                if i == 0:
                    # First row as headers
                    headers = row
                    all_text.append("| " + " | ".join(headers) + " |")
                    all_text.append("|" + "|".join(["---"] * len(headers)) + "|")
                else:
                    # Data rows
                    all_text.append("| " + " | ".join(row) + " |")
                    rows_data.append(row)
                    total_rows += 1

                    # Limit to prevent memory issues
                    if total_rows > 10000:
                        all_text.append(f"\n[...truncated at 10000 rows...]")
                        break

        except Exception as e:
            return ParsedContent(
                text=f"[Error parsing CSV: {e}]",
                title=path.stem,
                metadata={"error": str(e)}
            )

        metadata = {
            "format": "csv",
            "columns": headers,
            "column_count": len(headers),
            "row_count": total_rows,
            "sample_data": rows_data[:100],  # First 100 rows
        }

        return ParsedContent(
            text="\n".join(all_text),
            title=f"{path.stem} ({total_rows} rows, {len(headers)} columns)",
            metadata=metadata,
        )


__all__ = ["CSVParser"]
