# Release notes

This file describes the current fork changes compared with the original `PhantomPhoton/S3-Compatible` integration.

## Current fork changes

- Added Russian translation.
- Added `README-ru.md` and linked it from the main README.
- Added explicit S3 bucket addressing style support:
  - `path`
  - `virtual`
  - `auto`
- Changed the default addressing style to `path` for better compatibility with self-hosted S3 providers.
- Improved Garage compatibility for path-style S3 endpoints.
- Normalized endpoint URLs entered in the config flow.
- Normalized backup prefixes so a leading `/` is not stored as part of object keys.
- Added an options flow for changing non-secret settings after setup:
  - prefix
  - addressing style
  - custom CA verify path
- Moved blocking botocore setup validation, startup bucket checks, and automatic backup listing to Home Assistant executor jobs.
- Moved helper functions out of `const.py` into `helpers.py`.
- Kept constants in `const.py`, including backup cache and transfer-size constants.

## Notes

This repository keeps the Home Assistant integration domain:

```text
s3_compatible
```

Because the domain is shared with the original integration, Home Assistant analytics for `s3_compatible` may include installations that are not from this fork. The README intentionally does not show an installation-count badge.

This fork is intended to be installed as a HACS custom repository or manually copied into `custom_components/s3_compatible`.
