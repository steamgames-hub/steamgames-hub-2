import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Generator, List, Optional

from core.configuration.configuration import uploads_folder_name

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover - optional boto3 dependency
    boto3 = None
    ClientError = Exception

logger = logging.getLogger(__name__)


class StorageService:
    """Utility service that transparently stores files locally or in AWS S3.

    The service keeps backward compatibility with the previous local-only
    layout while enabling production deployments to push the payload to S3
    transparently.
    """

    def __init__(self) -> None:
        self._working_dir = os.getenv("WORKING_DIR", "")
        self._uploads_setting = uploads_folder_name()
        self._local_root = self._resolve_local_root()

        self._bucket = os.getenv("S3_BUCKET")
        self._region = os.getenv("S3_REGION")
        self._aws_key = os.getenv("AWS_ACCESS_KEY_ID")
        self._aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
        self._remote_prefix = self._resolve_remote_prefix()

        has_remote_config = all([self._bucket, self._region, self._aws_key, self._aws_secret])
        self._use_s3 = bool(has_remote_config and boto3 is not None)

        if self._use_s3:
            self._s3_client = boto3.client(
                "s3",
                aws_access_key_id=self._aws_key,
                aws_secret_access_key=self._aws_secret,
                region_name=self._region,
            )
            logger.info(
                "StorageService configured to use S3 bucket '%s' (prefix='%s')",
                self._bucket,
                self._remote_prefix,
            )
        else:
            self._s3_client = None
            if has_remote_config and boto3 is None:
                logger.warning("boto3 is not installed; falling back to local storage")

    def _resolve_local_root(self) -> str:
        uploads_dir = self._uploads_setting
        if os.path.isabs(uploads_dir):
            return uploads_dir
        return os.path.join(self._working_dir, uploads_dir)

    def _resolve_remote_prefix(self) -> str:
        explicit_prefix = os.getenv("S3_PREFIX")
        if explicit_prefix:
            return self._normalize_key(explicit_prefix)
        uploads_dir = self._uploads_setting or "uploads"
        uploads_dir = uploads_dir.replace("\\", "/").strip("/")
        return uploads_dir or "uploads"

    def _refresh_local_context_if_needed(self) -> None:
        working_dir = os.getenv("WORKING_DIR", "")
        uploads_setting = uploads_folder_name()
        if working_dir != self._working_dir or uploads_setting != self._uploads_setting:
            self._working_dir = working_dir
            self._uploads_setting = uploads_setting
            self._local_root = self._resolve_local_root()
            self._remote_prefix = self._resolve_remote_prefix()

    def _normalize_key(self, path: str) -> str:
        cleaned = path.replace("\\", "/")
        segments = [segment for segment in cleaned.split("/") if segment]
        return "/".join(segments)

    def _local_path(self, relative_path: str) -> str:
        self._refresh_local_context_if_needed()
        return os.path.join(self._local_root, relative_path)

    def _s3_key(self, relative_path: str) -> str:
        self._refresh_local_context_if_needed()
        rel = self._normalize_key(relative_path)
        if not self._remote_prefix:
            return rel
        return rel and f"{self._remote_prefix}/{rel}" or self._remote_prefix

    def uses_s3(self) -> bool:
        return self._use_s3

    @staticmethod
    def dataset_subdir(user_id: int, dataset_id: int) -> str:
        return os.path.join(f"user_{user_id}", f"dataset_{dataset_id}")

    @staticmethod
    def dataset_file_path(user_id: int, dataset_id: int, filename: str) -> str:
        return os.path.join(StorageService.dataset_subdir(user_id, dataset_id), filename)

    @staticmethod
    def community_icon_path(community_id: int, filename: str) -> str:
        return os.path.join("communities", f"community_{community_id}", filename)

    def save_local_file(self, src_path: str, relative_dest: str, remove_source: bool = True) -> str:
        """Store a file from disk into the configured backend."""
        if self._use_s3:
            key = self._s3_key(relative_dest)
            self._s3_client.upload_file(src_path, self._bucket, key)
            if remove_source:
                os.remove(src_path)
        else:
            dest_abs = self._local_path(relative_dest)
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            if remove_source:
                shutil.move(src_path, dest_abs)
            else:
                shutil.copy2(src_path, dest_abs)
        return relative_dest

    def save_fileobj(self, file_obj, relative_dest: str) -> str:
        """Store an in-memory FileStorage-like object into the backend."""
        if self._use_s3:
            key = self._s3_key(relative_dest)
            file_obj.stream.seek(0)
            self._s3_client.upload_fileobj(file_obj.stream, self._bucket, key)
        else:
            dest_abs = self._local_path(relative_dest)
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            file_obj.stream.seek(0)
            with open(dest_abs, "wb") as dest:
                shutil.copyfileobj(file_obj.stream, dest)
        return relative_dest

    def get_local_path(self, relative_path: str) -> str:
        """Return the absolute local path (always inside uploads)."""
        return self._local_path(relative_path)

    def ensure_local_copy(self, relative_path: str) -> str:
        """Download remote object if needed and return local path."""
        abs_path = self._local_path(relative_path)
        if self._use_s3 and not os.path.exists(abs_path):
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            self._s3_client.download_file(
                self._bucket,
                self._s3_key(relative_path),
                abs_path,
            )
        return abs_path

    def exists(self, relative_path: str) -> bool:
        if self._use_s3:
            try:
                self._s3_client.head_object(Bucket=self._bucket, Key=self._s3_key(relative_path))
                return True
            except ClientError:
                return False
        return os.path.exists(self._local_path(relative_path))

    def read_text(
        self,
        relative_path: str,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> str:
        if self._use_s3:
            obj = self._s3_client.get_object(Bucket=self._bucket, Key=self._s3_key(relative_path))
            return obj["Body"].read().decode(encoding, errors)
        with open(
            self._local_path(relative_path),
            "r",
            encoding=encoding,
            errors=errors,
        ) as handler:
            return handler.read()

    def open_binary(self, relative_path: str):
        if self._use_s3:
            obj = self._s3_client.get_object(Bucket=self._bucket, Key=self._s3_key(relative_path))
            return obj["Body"]
        return open(self._local_path(relative_path), "rb")

    def download_to_tempfile(self, relative_path: str) -> str:
        if self._use_s3:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            with temp_file as tmp:
                self._s3_client.download_fileobj(self._bucket, self._s3_key(relative_path), tmp)
            return temp_file.name
        return self._local_path(relative_path)

    def list_files(self, relative_dir: str) -> List[str]:
        """Return file keys inside the directory (processed recursively)."""
        results: List[str] = []
        normalized_dir = self._normalize_key(relative_dir)
        if self._use_s3:
            prefix = self._s3_key(normalized_dir)
            paginator = self._s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for content in page.get("Contents", []):
                    key = content["Key"]
                    rel = key[len(self._remote_prefix) + 1 :] if self._remote_prefix else key
                    results.append(rel)
        else:
            base = self._local_path(normalized_dir)
            if not os.path.isdir(base):
                return []
            for root, _, files in os.walk(base):
                for filename in files:
                    abs_path = os.path.join(root, filename)
                    rel = os.path.relpath(abs_path, self._local_root)
                    results.append(rel.replace("\\", "/"))
        return results

    @contextmanager
    def as_local_path(self, relative_path: str) -> Generator[str, None, None]:
        if self._use_s3:
            temp_path = self.download_to_tempfile(relative_path)
            try:
                yield temp_path
            finally:
                try:
                    os.remove(temp_path)
                except FileNotFoundError:
                    pass
        else:
            yield self._local_path(relative_path)

    def generate_presigned_url(self, relative_path: str, expires_in: int = 600) -> Optional[str]:
        if not self._use_s3:
            return None
        return self._s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": self._s3_key(relative_path),
            },
            ExpiresIn=expires_in,
        )


storage_service = StorageService()
