from __future__ import annotations

import csv
import os
from typing import List


class SteamCSVService:
    type_key = "steamcsv"

    REQUIRED_HEADERS: List[str] = [
        "appid",
        "name",
        "release_date",
        "is_free",
        "developers",
        "publishers",
        "platforms",
        "genres",
        "tags",
    ]

    def validate_folder(self, folder_path: str) -> None:
        if not os.path.isdir(folder_path):
            return  # Nothing to validate

        errors: List[str] = []
        found_csv = False

        for entry in os.listdir(folder_path):
            if not entry.lower().endswith(".csv"):
                continue  # Ignore non-CSV files
            found_csv = True
            msg = self._validate_csv_file(folder_path, entry)
            if msg:
                errors.append(msg)

        # Require at least one CSV file for steamcsv datasets
        if not found_csv:
            raise ValueError("No .csv files found for Steam CSV dataset type")

        if errors:
            raise ValueError("; ".join(errors))

    def _validate_csv_file(self, folder_path: str, entry: str) -> str | None:
        fpath = os.path.join(folder_path, entry)
        try:
            with open(fpath, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                rows = list(reader)
        except Exception as exc:
            return f"{entry}: cannot read CSV ({exc})"

        if headers != self.REQUIRED_HEADERS:
            return (
                f"{entry}: invalid headers. Expected exactly: "
                f"{', '.join(self.REQUIRED_HEADERS)} in this order"
            )

        if not rows or all(not any(cell.strip() for cell in row) for row in rows):
            return f"{entry}: must contain at least one data row"

        for i, row in enumerate(rows, start=2):
            if len(row) != len(self.REQUIRED_HEADERS):
                return f"{entry}: row {i} does not match header column count"

        return None

    def files_block_partial(self) -> str:
        return "dataset/_files_block.html"
