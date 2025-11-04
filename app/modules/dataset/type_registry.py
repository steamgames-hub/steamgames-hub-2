from __future__ import annotations

from typing import Dict, Type
import importlib


class BaseDatasetService:
    """Interface for dataset-type-specific services."""

    type_key: str = "base"

    def validate_folder(self, folder_path: str) -> None:
        """Validate all pending files for this dataset type.
        Raise ValueError with a human-readable message if invalid.
        """

    def files_block_partial(self) -> str:
        """Return the Jinja partial to include in the dataset detail for files section."""
        return "dataset/types/base/_files_block.html"


_REGISTRY: Dict[str, Type[BaseDatasetService]] = {}


def register(service_cls: Type[BaseDatasetService]):
    _REGISTRY[service_cls.type_key] = service_cls
    return service_cls


def get_service(type_key: str) -> BaseDatasetService:
    service_cls = _REGISTRY.get(type_key)
    if not service_cls:
        # Try to dynamically import the module for this type to trigger @register
        try:
            importlib.import_module(f"app.modules.dataset.types.{type_key}.services")
            service_cls = _REGISTRY.get(type_key)
        except Exception:
            service_cls = None

    if not service_cls:
        # Default: treat as steamcsv for compatibility if unknown
        from app.modules.dataset.types.steamcsv.services import SteamCSVService

        return SteamCSVService()
    return service_cls()
