"""Helpers for the S3 Compatible integration."""

from botocore.config import Config
from botocore.session import get_session as get_botocore_session

from .const import (
    ADDRESSING_STYLES,
    DEFAULT_ADDRESSING_STYLE,
)


def normalize_endpoint_url(endpoint_url: str | None) -> str | None:
    """Normalize endpoint URL entered by the user."""
    if endpoint_url is None:
        return None
    return endpoint_url.strip().rstrip("/")


def normalize_prefix(prefix: str | None) -> str:
    """Normalize S3 object prefix.

    Prefix is a key prefix inside the bucket, not a URL path. A leading slash
    commonly causes confusing keys such as /backup.tar, so strip it. Keep a
    trailing slash when the user wants a folder-like prefix.
    """
    return (prefix or "").strip().lstrip("/")


def normalize_addressing_style(addressing_style: str | None) -> str:
    """Return a valid S3 addressing style."""
    if addressing_style in ADDRESSING_STYLES:
        return addressing_style
    return DEFAULT_ADDRESSING_STYLE


def make_boto_config(addressing_style: str = DEFAULT_ADDRESSING_STYLE) -> Config:
    """Return botocore config for S3-compatible providers."""
    return Config(
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        s3={"addressing_style": normalize_addressing_style(addressing_style)},
    )


def create_s3_client(
    *,
    endpoint_url: str | None,
    region_name: str | None,
    access_key_id: str,
    secret_access_key: str,
    addressing_style: str | None = DEFAULT_ADDRESSING_STYLE,
    verify: str | None = None,
):
    """Create a synchronous botocore S3 client.

    Botocore loads service definitions and CA bundles from disk while creating
    the client and sending the first request. Call this only from an executor
    job in Home Assistant async code.
    """
    return get_botocore_session().create_client(
        "s3",
        endpoint_url=normalize_endpoint_url(endpoint_url),
        region_name=region_name,
        aws_secret_access_key=secret_access_key,
        aws_access_key_id=access_key_id,
        config=make_boto_config(addressing_style or DEFAULT_ADDRESSING_STYLE),
        verify=verify or None,
    )
