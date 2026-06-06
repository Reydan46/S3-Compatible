"""Config flow for the S3 Compatible integration."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError, ConnectionError, ParamValidationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    ADDRESSING_STYLES,
    CONF_ACCESS_KEY_ID,
    CONF_ADDRESSING_STYLE,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_VERIFY,
    DEFAULT_ADDRESSING_STYLE,
    DEFAULT_ENDPOINT_URL,
    DEFAULT_REGION,
    DESCRIPTION_AWS_S3_DOCS_URL,
    DESCRIPTION_BOTO3_DOCS_URL,
    DOMAIN,
)
from .helpers import (
    create_s3_client,
    normalize_addressing_style,
    normalize_endpoint_url,
    normalize_prefix,
)


def _addressing_style_selector() -> SelectSelector:
    """Return selector for S3 bucket addressing style."""
    return SelectSelector(
        SelectSelectorConfig(
            options=ADDRESSING_STYLES,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _user_data_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Return schema for initial setup."""
    defaults = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ACCESS_KEY_ID,
                default=defaults.get(CONF_ACCESS_KEY_ID, vol.UNDEFINED),
            ): cv.string,
            vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
                config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_BUCKET,
                default=defaults.get(CONF_BUCKET, vol.UNDEFINED),
            ): cv.string,
            vol.Required(
                CONF_REGION,
                default=defaults.get(CONF_REGION, DEFAULT_REGION),
            ): cv.string,
            vol.Optional(
                CONF_PREFIX,
                default=defaults.get(CONF_PREFIX, ""),
            ): cv.string,
            vol.Optional(
                CONF_ADDRESSING_STYLE,
                default=defaults.get(CONF_ADDRESSING_STYLE, DEFAULT_ADDRESSING_STYLE),
            ): _addressing_style_selector(),
            vol.Optional(
                CONF_VERIFY,
                default=defaults.get(CONF_VERIFY, ""),
            ): cv.string,
            vol.Required(
                CONF_ENDPOINT_URL,
                default=defaults.get(CONF_ENDPOINT_URL, DEFAULT_ENDPOINT_URL),
            ): TextSelector(config=TextSelectorConfig(type=TextSelectorType.URL)),
        }
    )


def _options_schema(config_entry: config_entries.ConfigEntry) -> vol.Schema:
    """Return schema for changing non-secret options."""
    data = config_entry.data
    options = config_entry.options
    return vol.Schema(
        {
            vol.Optional(
                CONF_PREFIX,
                default=options.get(CONF_PREFIX, data.get(CONF_PREFIX, "")),
            ): cv.string,
            vol.Optional(
                CONF_ADDRESSING_STYLE,
                default=options.get(
                    CONF_ADDRESSING_STYLE,
                    data.get(CONF_ADDRESSING_STYLE, DEFAULT_ADDRESSING_STYLE),
                ),
            ): _addressing_style_selector(),
            vol.Optional(
                CONF_VERIFY,
                default=options.get(CONF_VERIFY, data.get(CONF_VERIFY, "")),
            ): cv.string,
        }
    )


def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate S3 settings by checking bucket access."""
    errors: dict[str, str] = {}
    try:
        client = create_s3_client(
            endpoint_url=user_input.get(CONF_ENDPOINT_URL),
            region_name=user_input.get(CONF_REGION),
            secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
            access_key_id=user_input[CONF_ACCESS_KEY_ID],
            addressing_style=user_input.get(CONF_ADDRESSING_STYLE),
            verify=user_input.get(CONF_VERIFY) or None,
        )
        try:
            client.head_bucket(Bucket=user_input[CONF_BUCKET])
        finally:
            client.close()
    except ClientError:
        errors["base"] = "invalid_credentials"
    except ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            errors[CONF_BUCKET] = "invalid_bucket_name"
        else:
            errors["base"] = "unknown"
    except ValueError:
        errors[CONF_ENDPOINT_URL] = "invalid_endpoint_url"
    except ConnectionError:
        errors[CONF_ENDPOINT_URL] = "cannot_connect"
    except BotoCoreError:
        errors["base"] = "unknown"
    return errors


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize values before storing them in the config entry."""
    normalized = dict(user_input)
    normalized[CONF_ENDPOINT_URL] = normalize_endpoint_url(user_input.get(CONF_ENDPOINT_URL))
    normalized[CONF_PREFIX] = normalize_prefix(user_input.get(CONF_PREFIX))
    normalized[CONF_ADDRESSING_STYLE] = normalize_addressing_style(
        user_input.get(CONF_ADDRESSING_STYLE)
    )
    normalized[CONF_VERIFY] = (user_input.get(CONF_VERIFY) or "").strip()
    normalized[CONF_REGION] = (user_input.get(CONF_REGION) or DEFAULT_REGION).strip()
    return normalized


class S3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return S3OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_user_input(user_input)
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_ENDPOINT_URL: user_input[CONF_ENDPOINT_URL],
                }
            )

            errors = await self.hass.async_add_executor_job(
                _validate_input, user_input
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_data_schema(user_input),
            errors=errors,
            description_placeholders={
                "aws_s3_docs_url": DESCRIPTION_AWS_S3_DOCS_URL,
                "boto3_docs_url": DESCRIPTION_BOTO3_DOCS_URL,
            },
        )


class S3OptionsFlow(OptionsFlow):
    """Handle options for S3 Compatible."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage S3 Compatible options."""
        if user_input is not None:
            options = dict(user_input)
            options[CONF_PREFIX] = normalize_prefix(options.get(CONF_PREFIX))
            options[CONF_ADDRESSING_STYLE] = normalize_addressing_style(
                options.get(CONF_ADDRESSING_STYLE)
            )
            options[CONF_VERIFY] = (options.get(CONF_VERIFY) or "").strip()
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry),
        )
