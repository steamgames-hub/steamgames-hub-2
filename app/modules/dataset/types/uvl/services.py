from __future__ import annotations

import os

from app.modules.dataset.type_registry import BaseDatasetService, register


@register
class UVLService(BaseDatasetService):
    type_key = "uvl"

    def validate_folder(self, folder_path: str) -> None:
        # For UVL, perform a minimal validation: ensure there is at least one .uvl file.
        if not os.path.isdir(folder_path):
            return
        has_uvl = any(name.lower().endswith(".uvl") for name in os.listdir(folder_path))
        if not has_uvl:
            raise ValueError("No .uvl files found for UVL dataset type")

    def files_block_partial(self) -> str:
        return "dataset/types/uvl/_files_block.html"
