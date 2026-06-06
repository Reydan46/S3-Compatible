"""The S3 Compatible integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from botocore.exceptions import BotoCoreError, ClientError, ConnectionError, ParamValidationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
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
)
from .helpers import (
    create_s3_client,
    normalize_addressing_style,
    normalize_endpoint_url,
    normalize_prefix,
)

type S3ConfigEntry = ConfigEntry[Any]


_LOGGER = logging.getLogger(__name__)


def entry_value(entry: ConfigEntry, key: str, default: str | None = None) -> str | None:
    """Return an option value, falling back to config entry data."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current schema."""
    data = dict(entry.data)
    options = dict(entry.options)

    data[CONF_ENDPOINT_URL] = normalize_endpoint_url(data.get(CONF_ENDPOINT_URL))
    data[CONF_PREFIX] = normalize_prefix(data.get(CONF_PREFIX))
    data[CONF_ADDRESSING_STYLE] = normalize_addressing_style(
        data.get(CONF_ADDRESSING_STYLE, DEFAULT_ADDRESSING_STYLE)
    )
    data[CONF_VERIFY] = (data.get(CONF_VERIFY) or "").strip()

    if CONF_PREFIX in options:
        options[CONF_PREFIX] = normalize_prefix(options.get(CONF_PREFIX))
    if CONF_ADDRESSING_STYLE in options:
        options[CONF_ADDRESSING_STYLE] = normalize_addressing_style(
            options.get(CONF_ADDRESSING_STYLE)
        )
    if CONF_VERIFY in options:
        options[CONF_VERIFY] = (options.get(CONF_VERIFY) or "").strip()

    if data != entry.data or options != entry.options or entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=2,
        )

    return True


def _validate_entry(data: dict, addressing_style: str, verify: str | None) -> None:
    """Validate stored S3 settings by checking bucket access."""
    client = create_s3_client(
        endpoint_url=data.get(CONF_ENDPOINT_URL),
        region_name=data.get(CONF_REGION),
        secret_access_key=data[CONF_SECRET_ACCESS_KEY],
        access_key_id=data[CONF_ACCESS_KEY_ID],
        addressing_style=addressing_style,
        verify=verify,
    )
    try:
        client.head_bucket(Bucket=data[CONF_BUCKET])
    finally:
        client.close()


async def async_setup_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Set up S3 from a config entry."""

    data = cast("dict", entry.data)
    addressing_style = normalize_addressing_style(
        entry_value(entry, CONF_ADDRESSING_STYLE, DEFAULT_ADDRESSING_STYLE)
    )
    verify = entry_value(entry, CONF_VERIFY, "") or None

    try:
        await hass.async_add_executor_job(_validate_entry, data, addressing_style, verify)
    except ClientError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_bucket_name",
            ) from err
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ValueError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_endpoint_url",
        ) from err
    except ConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except BotoCoreError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
