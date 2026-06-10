from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Optional

from google.cloud import storage


class GCSHelper:
    """
    Helper class for interacting with Google Cloud Storage.
    """

    def __init__(self, bucket_name: str):
        """
        Initialize GCS helper.

        Args:
            bucket_name (str):
                Target GCS bucket name.
        """
        if not bucket_name:
            raise ValueError("bucket_name is required")

        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_file(
        self,
        local_path: str | Path,
        blob_name: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a local file to GCS.

        Args:
            local_path (str | Path):
                Local file path.

            blob_name (str):
                Destination blob path in GCS.

            content_type (Optional[str]):
                MIME type.

        Returns:
            str:
                GCS URI.

        Example:
            local_path = "temp/output/report.pdf"
            blob_name = "reports/report.pdf"
        """
        local_path = Path(local_path)

        if not local_path.exists():
            raise FileNotFoundError(
                f"Local file not found: {local_path}"
            )

        blob = self.bucket.blob(blob_name)

        if content_type:
            blob.content_type = content_type

        blob.upload_from_filename(
            str(local_path)
        )

        return f"gs://{self.bucket.name}/{blob_name}"

    def download_file(
        self,
        blob_name: str,
        local_path: str | Path,
    ) -> Path:
        """
        Download a file from GCS.

        Args:
            blob_name (str):
                Blob name in bucket.

            local_path (str | Path):
                Local destination path.

        Returns:
            Path:
                Downloaded file path.
        """
        local_path = Path(local_path)

        local_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        blob = self.bucket.blob(blob_name)

        if not blob.exists():
            raise FileNotFoundError(
                f"Blob not found: "
                f"gs://{self.bucket.name}/{blob_name}"
            )

        blob.download_to_filename(
            str(local_path)
        )

        return local_path

    def list_blobs(
        self,
        prefix: str = "",
    ) -> list[str]:
        """
        List all blobs under a prefix.

        Args:
            prefix (str):
                GCS folder prefix.

        Returns:
            list[str]:
                Blob names.
        """
        return [
            blob.name
            for blob in self.bucket.list_blobs(
                prefix=prefix
            )
        ]

    def delete_blob(
        self,
        blob_name: str,
    ) -> None:
        """
        Delete a blob if it exists.

        Args:
            blob_name (str):
                Blob name.
        """
        blob = self.bucket.blob(blob_name)

        if blob.exists():
            blob.delete()

    def make_blob_public(
        self,
        blob_name: str,
    ) -> str:
        """
        Make a blob publicly accessible and return its HTTPS URL.

        Args:
            blob_name (str):
                Blob path inside the bucket.

        Returns:
            str:
                Public HTTPS URL.
        """
        blob = self.bucket.blob(blob_name)

        if not blob.exists():
            raise FileNotFoundError(
                f"Blob not found: gs://{self.bucket.name}/{blob_name}"
            )

        blob.make_public()

        return blob.public_url