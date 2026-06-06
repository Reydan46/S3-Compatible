[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

# S3 Compatible for Home Assistant

[Русская версия README](README-ru.md)

A Home Assistant custom integration for using S3-compatible object storage as a backup target.

This fork is based on the original [PhantomPhoton/S3-Compatible](https://github.com/PhantomPhoton/S3-Compatible) integration and adds better support for S3-compatible providers that require **path-style addressing**, such as [Garage](https://garagehq.deuxfleurs.fr/).

## Features

- Adds an S3-compatible backup location to Home Assistant backups.
- Supports path-style, virtual-hosted-style, and automatic S3 bucket addressing.
- Defaults to `path` addressing for better compatibility with self-hosted S3 providers.
- Supports empty or folder-like object prefixes.
- Normalizes endpoint URLs and prefixes entered in the config flow.
- Provides an options flow for changing non-secret settings after setup.
- Includes English and Russian translations.
- Avoids blocking Home Assistant's event loop during setup validation, startup bucket checks, and automatic backup listing by running blocking botocore calls in an executor.

## Known working services

The integration should work with most S3-compatible providers. Known or expected targets include:

- [Amazon S3](https://aws.amazon.com/s3/)
- [Garage](https://garagehq.deuxfleurs.fr/)
- [MinIO](https://min.io)
- [MEGA S4](https://mega.io/objectstorage)
- [Scaleway Object Storage](https://www.scaleway.com/en/object-storage/)
- [Storj](https://www.storj.io/cloud-object-storage)
- [Cloudflare R2](https://www.cloudflare.com/developer-platform/products/r2/)
- [Backblaze B2](https://www.backblaze.com/cloud-storage)
- [IDrive e2](https://www.idrive.com/s3-storage-e2/)
- [Hetzner Object Storage](https://www.hetzner.com/storage/object-storage/)
- [SeaweedFS](https://seaweedfs.com)
- [e24cloud](https://www.e24cloud.com/en/api-e24files/)
- [OVHcloud Object Storage](https://www.ovhcloud.com/)

## Installation

### Option A: HACS custom repository

1. Open HACS.
2. Go to **Integrations**.
3. Open the three-dot menu and select **Custom repositories**.
4. Add this repository URL:

   ```text
   https://github.com/Reydan46/S3-Compatible
   ```

5. Select category **Integration**.
6. Install **S3 Compatible**.
7. Restart Home Assistant.
8. Add a new backup target:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=s3_compatible)

### Option B: Manual installation

1. Copy this directory:

   ```text
   custom_components/s3_compatible
   ```

   to your Home Assistant config directory:

   ```text
   /config/custom_components/s3_compatible
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & services**.
4. Click **Add Integration**.
5. Search for **S3 Compatible**.
6. Follow the setup flow.

## Configuration

The setup form asks for:

| Field | Description |
| --- | --- |
| Access key ID | S3 access key. |
| Secret access key | S3 secret key. |
| Bucket name | Bucket where Home Assistant backups will be stored. |
| Region | S3 signing region. Many S3-compatible providers accept `us-east-1`; Garage commonly works with the configured Garage region, often `garage` or `us-east-1` depending on your setup. |
| Prefix | Optional object key prefix inside the bucket, for example `homeassistant/`. Leave empty to store backups at the bucket root. |
| Addressing style | S3 bucket addressing mode: `path`, `virtual`, or `auto`. |
| Verify | Optional custom CA bundle path. Leave empty for the default system/certifi CA bundle. |
| Endpoint URL | S3 API endpoint URL, without bucket name or prefix. |

## Addressing style

Some S3-compatible providers support only one bucket addressing style.

### Path-style

Path-style sends requests like this:

```text
https://s3.example.com/my-bucket/path/to/object
```

Use this for Garage and many self-hosted S3 deployments.

### Virtual-hosted-style

Virtual-hosted-style sends requests like this:

```text
https://my-bucket.s3.example.com/path/to/object
```

Use this for providers that require bucket names in the hostname.

### Auto

`auto` lets botocore decide. For self-hosted providers, explicit `path` is usually safer.

## Garage example

For a Garage S3 endpoint such as:

```text
https://s3-backup.example.com
```

and bucket:

```text
hass-backup
```

use:

| Field | Value |
| --- | --- |
| Endpoint URL | `https://s3-backup.example.com` |
| Bucket name | `hass-backup` |
| Region | `garage` or `us-east-1` |
| Prefix | empty, or `homeassistant/` |
| Addressing style | `path` |

Do **not** put the bucket name in the endpoint URL.

Correct:

```text
Endpoint URL: https://s3-backup.example.com
Bucket name:  hass-backup
```

Incorrect:

```text
Endpoint URL: https://s3-backup.example.com/hass-backup
```

## Changing options after setup

After the integration is created, the options flow can change:

- Prefix
- Addressing style
- Verify / custom CA bundle path

For secret changes, such as access key or secret key, delete and recreate the integration entry.

## Troubleshooting

### `ListObjectsV2` returns 500 Internal Server Error

For Garage and other path-style providers, verify:

- Endpoint URL does not include the bucket name.
- Bucket name is set in the bucket field.
- Addressing style is `path`.
- Prefix is empty or a key prefix like `homeassistant/`, without a leading `/`.
- Your reverse proxy forwards the path unchanged.
- The request reaches the S3 API endpoint, not a static website endpoint.

For path-style, the provider should receive requests shaped like:

```text
GET /hass-backup?list-type=2
Host: s3-backup.example.com
```

not:

```text
GET /?list-type=2
Host: hass-backup.s3-backup.example.com
```

### Home Assistant logs blocking-call warnings

This fork moves setup validation, startup bucket checks, and automatic backup listing to Home Assistant's executor to avoid blocking the event loop with botocore filesystem and SSL setup calls.

If you still see blocking-call warnings, please open an issue with:

- Home Assistant version
- Integration version
- Operation being performed: setup, startup, list, upload, download, delete
- Full traceback with secrets removed

## Credits

Based on:

- The official Home Assistant [AWS S3](https://www.home-assistant.io/integrations/aws_s3) integration
- The original [PhantomPhoton/S3-Compatible](https://github.com/PhantomPhoton/S3-Compatible) custom integration
