"""Constants for the S3 Compatible integration."""
from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "s3_compatible"

CONF_ACCESS_KEY_ID: Final = "access_key_id"
CONF_SECRET_ACCESS_KEY: Final = "secret_access_key"
CONF_ENDPOINT_URL: Final = "endpoint_url"
CONF_BUCKET: Final = "bucket"
CONF_PREFIX: Final = "prefix"
CONF_REGION: Final = "region"
CONF_VERIFY: Final = "verify"
CONF_ADDRESSING_STYLE: Final = "addressing_style"

ADDRESSING_STYLE_AUTO: Final = "auto"
ADDRESSING_STYLE_VIRTUAL: Final = "virtual"
ADDRESSING_STYLE_PATH: Final = "path"
ADDRESSING_STYLES: Final = [
    ADDRESSING_STYLE_AUTO,
    ADDRESSING_STYLE_VIRTUAL,
    ADDRESSING_STYLE_PATH,
]

AWS_DOMAIN: Final = "amazonaws.com"
DEFAULT_REGION: Final = "us-east-1"
DEFAULT_ENDPOINT_URL: Final = f"https://s3.{DEFAULT_REGION}.{AWS_DOMAIN}/"
DEFAULT_ADDRESSING_STYLE: Final = ADDRESSING_STYLE_PATH

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

DESCRIPTION_AWS_S3_DOCS_URL: Final = "https://docs.aws.amazon.com/general/latest/gr/s3.html"
DESCRIPTION_BOTO3_DOCS_URL: Final = "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html"

CACHE_TTL: Final = 300

# S3 part size requirements: 5 MiB to 5 GiB per part.
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
# Use 20 MiB to avoid too many parts. Each part is allocated in memory.
MULTIPART_MIN_PART_SIZE_BYTES: Final = 20 * 2**20
DOWNLOAD_CHUNK_SIZE_BYTES: Final = 1024 * 1024
