"""Backup platform for the S3 Compatible integration."""

import functools
import json
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from time import time
from typing import Any, TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CACHE_TTL,
    CONF_ACCESS_KEY_ID,
    CONF_ADDRESSING_STYLE,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_VERIFY,
    DATA_BACKUP_AGENT_LISTENERS,
    DEFAULT_ADDRESSING_STYLE,
    DOMAIN,
    DOWNLOAD_CHUNK_SIZE_BYTES,
    MULTIPART_MIN_PART_SIZE_BYTES,
)
from .helpers import (
    create_s3_client,
    normalize_addressing_style,
    normalize_endpoint_url,
    normalize_prefix,
)

if TYPE_CHECKING:
    from . import S3ConfigEntry


_LOGGER = logging.getLogger(__name__)
S3_CLIENT_ERRORS = (BotoCoreError, ClientError)


def handle_boto_errors[T](
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Handle BotoCoreError exceptions by converting them to BackupAgentError."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """Catch BotoCoreError and raise BackupAgentError."""
        try:
            return await func(*args, **kwargs)
        except ClientError as err:
            response_metadata = err.response.get("ResponseMetadata", {})
            error = err.response.get("Error", {})
            _LOGGER.error(
                "S3 error during %s: operation=%s code=%s status=%s message=%s",
                func.__name__,
                err.operation_name,
                error.get("Code"),
                response_metadata.get("HTTPStatusCode"),
                error.get("Message"),
            )
            error_msg = f"Failed during {func.__name__}"
            raise BackupAgentError(error_msg) from err
        except BotoCoreError as err:
            error_msg = f"Failed during {func.__name__}"
            raise BackupAgentError(error_msg) from err

    return wrapper


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list["S3ConfigEntry"] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [S3BackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


def suggested_filenames(backup: AgentBackup, prefix: str) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata files."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{prefix}{base_name}.tar", f"{prefix}{base_name}.metadata.json"


class S3BackupAgent(BackupAgent):
    """Backup agent for the S3 integration."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: "S3ConfigEntry") -> None:
        """Initialize the S3 agent."""
        super().__init__()
        self.hass = hass
        self._access_key_id = entry.data[CONF_ACCESS_KEY_ID]
        self._secret_access_key = entry.data[CONF_SECRET_ACCESS_KEY]
        self._endpoint_url = normalize_endpoint_url(entry.data.get(CONF_ENDPOINT_URL))
        self._region = entry.data.get(CONF_REGION)
        self._addressing_style: str = normalize_addressing_style(
            entry.options.get(
                CONF_ADDRESSING_STYLE,
                entry.data.get(CONF_ADDRESSING_STYLE, DEFAULT_ADDRESSING_STYLE),
            )
        )

        self._bucket: str = entry.data[CONF_BUCKET]
        self._prefix: str = normalize_prefix(
            entry.options.get(CONF_PREFIX, entry.data.get(CONF_PREFIX, ""))
        )
        self._verify: str = (
            entry.options.get(CONF_VERIFY, entry.data.get(CONF_VERIFY, "")) or ""
        ).strip()

        self.name = entry.title
        self.unique_id = entry.entry_id
        self._backup_cache: dict[str, AgentBackup] = {}
        self._cache_expiration = time()
        _LOGGER.info(
            "Initialized S3 backup agent: endpoint=%s bucket=%s region=%s prefix=%r addressing_style=%s",
            self._endpoint_url,
            self._bucket,
            self._region,
            self._prefix,
            self._addressing_style,
        )

    def _create_sync_client(self):
        """Create a synchronous S3 client for executor jobs."""
        return create_s3_client(
            endpoint_url=self._endpoint_url,
            region_name=self._region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            addressing_style=self._addressing_style,
            verify=self._verify or None,
        )

    @handle_boto_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        backup = await self._find_backup_by_id(backup_id)
        tar_filename, _ = suggested_filenames(backup, self._prefix)

        client = await self.hass.async_add_executor_job(self._create_sync_client)
        try:
            response = await self.hass.async_add_executor_job(
                self._get_object_sync,
                client,
                tar_filename,
            )
        except S3_CLIENT_ERRORS:
            await self.hass.async_add_executor_job(client.close)
            raise

        return self._download_backup_chunks(client, response["Body"])

    async def _download_backup_chunks(self, client: Any, body: Any) -> AsyncIterator[bytes]:
        """Download a backup as chunks without blocking the event loop."""
        try:
            try:
                while chunk := await self.hass.async_add_executor_job(
                    body.read,
                    DOWNLOAD_CHUNK_SIZE_BYTES,
                ):
                    yield chunk
            except S3_CLIENT_ERRORS as err:
                raise BackupAgentError("Failed during async_download_backup") from err
        finally:
            await self.hass.async_add_executor_job(body.close)
            await self.hass.async_add_executor_job(client.close)

    def _get_object_sync(self, client: Any, key: str) -> dict[str, Any]:
        """Get an object synchronously. Must be called from an executor job."""
        return client.get_object(Bucket=self._bucket, Key=key)

    @handle_boto_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        """
        tar_filename, metadata_filename = suggested_filenames(backup, self._prefix)

        if backup.size < MULTIPART_MIN_PART_SIZE_BYTES:
            await self._upload_simple(tar_filename, open_stream)
        else:
            await self._upload_multipart(tar_filename, open_stream)

        # Upload the metadata file
        metadata_content = json.dumps(backup.as_dict())
        await self.hass.async_add_executor_job(
            self._put_object_sync,
            metadata_filename,
            metadata_content,
        )
        self._invalidate_cache()

    async def _upload_simple(
        self,
        tar_filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
    ) -> None:
        """Upload a small file using simple upload.

        :param tar_filename: The target filename for the backup.
        :param open_stream: A function returning an async iterator that yields bytes.
        """
        _LOGGER.info("Starting simple upload for %s", tar_filename)
        stream = await open_stream()
        file_data = bytearray()
        async for chunk in stream:
            file_data.extend(chunk)

        await self.hass.async_add_executor_job(
            self._put_object_sync,
            tar_filename,
            bytes(file_data),
        )

    async def _upload_multipart(
        self,
        tar_filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
    ):
        """Upload a large file using multipart upload.

        :param tar_filename: The target filename for the backup.
        :param open_stream: A function returning an async iterator that yields bytes.
        """
        _LOGGER.info("Starting multipart upload for %s", tar_filename)

        upload_id = await self.hass.async_add_executor_job(
            self._create_multipart_upload_sync,
            tar_filename,
        )
        try:
            parts = []
            part_number = 1
            buffer_size = 0  # bytes
            buffer: bytearray = bytearray()

            stream = await open_stream()
            async for chunk in stream:
                buffer.extend(chunk)
                buffer_size = len(buffer)

                # If buffer size meets minimum part size, upload it as a part
                if buffer_size >= MULTIPART_MIN_PART_SIZE_BYTES:
                    # Mega S4 requires all parts to be exactly the same size
                    overflow = buffer[MULTIPART_MIN_PART_SIZE_BYTES:]
                    buffer = buffer[:MULTIPART_MIN_PART_SIZE_BYTES]
                    buffer_size = len(buffer)

                    _LOGGER.info(
                        "Uploading part number %d, size %d",
                        part_number,
                        buffer_size,
                    )
                    etag = await self.hass.async_add_executor_job(
                        self._upload_part_sync,
                        tar_filename,
                        upload_id,
                        part_number,
                        bytes(buffer),
                    )
                    parts.append({"PartNumber": part_number, "ETag": etag})
                    part_number += 1
                    buffer = overflow
                    buffer_size = len(buffer)

            # Upload the final buffer as the last part (no minimum size requirement)
            if buffer:
                _LOGGER.info(
                    "Uploading final part number %d, size %d",
                    part_number,
                    buffer_size,
                )
                etag = await self.hass.async_add_executor_job(
                    self._upload_part_sync,
                    tar_filename,
                    upload_id,
                    part_number,
                    bytes(buffer),
                )
                parts.append({"PartNumber": part_number, "ETag": etag})

            await self.hass.async_add_executor_job(
                self._complete_multipart_upload_sync,
                tar_filename,
                upload_id,
                parts,
            )

        except S3_CLIENT_ERRORS:
            try:
                await self.hass.async_add_executor_job(
                    self._abort_multipart_upload_sync,
                    tar_filename,
                    upload_id,
                )
            except S3_CLIENT_ERRORS:
                _LOGGER.exception("Failed to abort multipart upload")
            raise

    def _put_object_sync(self, key: str, body: bytes | str) -> None:
        """Upload an object synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            client.put_object(Bucket=self._bucket, Key=key, Body=body)
        finally:
            client.close()

    def _create_multipart_upload_sync(self, key: str) -> str:
        """Create multipart upload synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            multipart_upload = client.create_multipart_upload(
                Bucket=self._bucket,
                Key=key,
            )
            return multipart_upload["UploadId"]
        finally:
            client.close()

    def _upload_part_sync(
        self,
        key: str,
        upload_id: str,
        part_number: int,
        body: bytes,
    ) -> str:
        """Upload a multipart part synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            part = client.upload_part(
                Bucket=self._bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=body,
            )
            return part["ETag"]
        finally:
            client.close()

    def _complete_multipart_upload_sync(
        self,
        key: str,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> None:
        """Complete multipart upload synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        finally:
            client.close()

    def _abort_multipart_upload_sync(self, key: str, upload_id: str) -> None:
        """Abort multipart upload synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            client.abort_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
            )
        finally:
            client.close()

    @handle_boto_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)
        tar_filename, metadata_filename = suggested_filenames(backup, self._prefix)

        # Delete both the backup file and its metadata file
        await self.hass.async_add_executor_job(
            self._delete_backup_objects_sync,
            tar_filename,
            metadata_filename,
        )

        # Reset cache after successful deletion
        self._invalidate_cache()

    def _delete_backup_objects_sync(
        self,
        tar_filename: str,
        metadata_filename: str,
    ) -> None:
        """Delete backup objects synchronously. Must be called from an executor job."""
        client = self._create_sync_client()
        try:
            client.delete_object(Bucket=self._bucket, Key=tar_filename)
            client.delete_object(Bucket=self._bucket, Key=metadata_filename)
        finally:
            client.close()

    @handle_boto_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups = await self._list_backups()
        return list(backups.values())

    @handle_boto_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID."""
        backups = await self._list_backups()
        if backup := backups.get(backup_id):
            return backup

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def _list_backups(self) -> dict[str, AgentBackup]:
        """List backups, using a cache if possible."""
        if time() <= self._cache_expiration:
            return self._backup_cache

        self._backup_cache = await self.hass.async_add_executor_job(
            self._list_backups_sync
        )
        self._cache_expiration = time() + CACHE_TTL

        return self._backup_cache

    def _invalidate_cache(self) -> None:
        """Invalidate cached backup metadata after remote changes."""
        self._backup_cache = {}
        self._cache_expiration = 0

    def _list_backups_sync(self) -> dict[str, AgentBackup]:
        """List backups synchronously. Must be called from an executor job."""
        backups: dict[str, AgentBackup] = {}
        client = self._create_sync_client()
        try:
            list_kwargs = {"Bucket": self._bucket}
            if self._prefix:
                list_kwargs["Prefix"] = self._prefix
            paginator = client.get_paginator("list_objects_v2")

            for page in paginator.paginate(**list_kwargs):
                metadata_files = [
                    obj
                    for obj in page.get("Contents", [])
                    if obj["Key"].endswith(".metadata.json")
                ]

                for metadata_file in metadata_files:
                    try:
                        metadata_json = self._read_metadata_sync(
                            client, metadata_file["Key"]
                        )
                    except (BotoCoreError, ClientError, json.JSONDecodeError) as err:
                        _LOGGER.warning(
                            "Failed to process metadata file %s: %s",
                            metadata_file["Key"],
                            err,
                        )
                        continue
                    if "addons" not in metadata_json:
                        metadata_json["addons"] = []
                    backup = AgentBackup.from_dict(metadata_json)
                    backups[backup.backup_id] = backup
        finally:
            client.close()

        return backups

    def _read_metadata_sync(self, client: Any, key: str) -> dict[str, Any]:
        """Read backup metadata synchronously and close the response body."""
        metadata_response = client.get_object(Bucket=self._bucket, Key=key)
        body = metadata_response["Body"]
        try:
            return json.loads(body.read())
        finally:
            body.close()
