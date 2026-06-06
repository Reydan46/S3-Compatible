[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

# S3 Compatible для Home Assistant

[English README](README.md)

Кастомная интеграция Home Assistant, которая добавляет S3-совместимое объектное хранилище как место хранения резервных копий.

Этот fork основан на оригинальной интеграции [PhantomPhoton/S3-Compatible](https://github.com/PhantomPhoton/S3-Compatible) и добавляет более полноценную поддержку S3-провайдеров, которым нужен **path-style addressing**, например [Garage](https://garagehq.deuxfleurs.fr/).

## Возможности

- Добавляет S3-совместимое хранилище как backup location в Home Assistant.
- Поддерживает режимы адресации bucket: `path`, `virtual`, `auto`.
- По умолчанию использует `path`, что лучше подходит для self-hosted S3-провайдеров.
- Поддерживает пустой prefix и folder-like prefix, например `homeassistant/`.
- Нормализует endpoint URL и prefix, введённые в config flow.
- Позволяет менять не-секретные параметры через options flow после создания записи.
- Содержит английскую и русскую локализации.
- Не блокирует event loop Home Assistant при проверке настроек, проверке bucket на старте и автоматическом списке бэкапов: блокирующие вызовы botocore выполняются через executor.

## Известные совместимые сервисы

Интеграция должна работать с большинством S3-совместимых провайдеров. Известные или ожидаемые варианты:

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

## Установка

### Вариант A: HACS custom repository

1. Откройте HACS.
2. Перейдите в **Integrations**.
3. Откройте меню с тремя точками и выберите **Custom repositories**.
4. Добавьте URL репозитория:

   ```text
   https://github.com/Reydan46/S3-Compatible
   ```

5. Выберите категорию **Integration**.
6. Установите **S3 Compatible**.
7. Перезапустите Home Assistant.
8. Добавьте новое место хранения backup:

   [![Открыть Home Assistant и начать настройку интеграции.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=s3_compatible)

### Вариант B: ручная установка

1. Скопируйте папку:

   ```text
   custom_components/s3_compatible
   ```

   в директорию конфигурации Home Assistant:

   ```text
   /config/custom_components/s3_compatible
   ```

2. Перезапустите Home Assistant.
3. Откройте **Настройки → Устройства и службы**.
4. Нажмите **Добавить интеграцию**.
5. Найдите **S3 Compatible**.
6. Пройдите мастер настройки.

## Настройка

Форма настройки содержит поля:

| Поле | Описание |
| --- | --- |
| Access key ID | S3 access key. |
| Secret access key | S3 secret key. |
| Bucket name | Bucket, куда Home Assistant будет сохранять резервные копии. |
| Region | Регион для S3-подписи. Многие S3-compatible провайдеры принимают `us-east-1`; для Garage может использоваться регион из конфигурации Garage, часто `garage` или `us-east-1`. |
| Prefix | Необязательный prefix ключей внутри bucket, например `homeassistant/`. Оставьте пустым, чтобы хранить backup в корне bucket. |
| Addressing style | Режим адресации bucket: `path`, `virtual` или `auto`. |
| Verify | Необязательный путь к custom CA bundle. Оставьте пустым, чтобы использовать стандартный системный/certifi CA bundle. |
| Endpoint URL | URL S3 API endpoint без имени bucket и без prefix. |

## Режим адресации bucket

Разные S3-compatible провайдеры могут поддерживать разные способы адресации bucket.

### Path-style

Path-style отправляет запросы так:

```text
https://s3.example.com/my-bucket/path/to/object
```

Используйте этот режим для Garage и многих self-hosted S3-инсталляций.

### Virtual-hosted-style

Virtual-hosted-style отправляет запросы так:

```text
https://my-bucket.s3.example.com/path/to/object
```

Используйте этот режим для провайдеров, которым нужно имя bucket в hostname.

### Auto

`auto` позволяет botocore выбрать режим автоматически. Для self-hosted провайдеров обычно безопаснее явно выбрать `path`.

## Пример для Garage

Если S3 endpoint Garage:

```text
https://s3-backup.example.com
```

а bucket:

```text
hass-backup
```

используйте:

| Поле | Значение |
| --- | --- |
| Endpoint URL | `https://s3-backup.example.com` |
| Bucket name | `hass-backup` |
| Region | `garage` или `us-east-1` |
| Prefix | пусто или `homeassistant/` |
| Addressing style | `path` |

Не добавляйте имя bucket в endpoint URL.

Правильно:

```text
Endpoint URL: https://s3-backup.example.com
Bucket name:  hass-backup
```

Неправильно:

```text
Endpoint URL: https://s3-backup.example.com/hass-backup
```

## Изменение настроек после создания записи

После создания integration entry через options flow можно изменить:

- Prefix
- Addressing style
- Verify / путь к custom CA bundle

Для изменения секретов, например access key или secret key, удалите запись интеграции и создайте её заново.

## Troubleshooting

### `ListObjectsV2` возвращает 500 Internal Server Error

Для Garage и других path-style провайдеров проверьте:

- Endpoint URL не содержит имя bucket.
- Bucket указан отдельным полем.
- Addressing style установлен в `path`.
- Prefix пустой или выглядит как `homeassistant/`, без ведущего `/`.
- Reverse proxy не переписывает path.
- Запрос попадает именно в S3 API endpoint, а не в static website endpoint.

Для path-style провайдер должен получать запросы примерно такого вида:

```text
GET /hass-backup?list-type=2
Host: s3-backup.example.com
```

а не:

```text
GET /?list-type=2
Host: hass-backup.s3-backup.example.com
```

### Home Assistant пишет `Detected blocking call`

Этот fork переносит проверку настроек, проверку bucket при старте и автоматический список backup в executor Home Assistant. Это нужно, потому что botocore может синхронно читать файлы service definitions и CA bundle.

Если предупреждения всё равно появляются, создайте issue и приложите:

- версию Home Assistant;
- версию интеграции;
- действие, при котором появляется warning: setup, startup, list, upload, download, delete;
- полный traceback без секретов.

## Credits

Основано на:

- официальной интеграции Home Assistant [AWS S3](https://www.home-assistant.io/integrations/aws_s3)
- оригинальной кастомной интеграции [PhantomPhoton/S3-Compatible](https://github.com/PhantomPhoton/S3-Compatible)
