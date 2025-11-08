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
                # Ignore non-CSV files for this type
                continue
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
        except Exception as exc:
            return f"{entry}: cannot read CSV ({exc})"

        # Compare headers case-insensitively and ignoring extra spaces
        present = {str(h).strip().lower() for h in headers}
        missing = []
        for h in self.REQUIRED_HEADERS:
            if h.strip().lower() not in present:
                missing.append(h)
        if missing:
            return f"{entry}: missing headers {', '.join(missing)}"
        return None

    def files_block_partial(self) -> str:
        # New flattened template path (no 'types' folder)
        return "dataset/_files_block.html"
