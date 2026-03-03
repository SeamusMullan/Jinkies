# Configuration Reference

Jinkies stores its configuration in `config.json` in the platform-appropriate directory:

- **Linux:** `~/.config/jinkies/config.json`
- **macOS:** `~/Library/Application Support/jinkies/config.json`
- **Windows:** `%APPDATA%\jinkies\config.json`

The file is managed automatically by the application, but you can edit it manually while Jinkies is not running.

---

## Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `poll_interval_secs` | integer | `60` | Seconds between feed poll cycles. |
| `feeds` | array of [Feed](#feed-object) | `[]` | List of feeds to monitor. |
| `sound_map` | object | see [Sound map](#sound_map) | Mapping of event names to WAV file paths. |
| `notification_style` | string | `"native"` | Notification style. Valid values: `"native"`, `"custom"`. |

---

## `feeds` — Feed object

Each entry in the `feeds` array is an object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | yes | The Atom/RSS feed URL. |
| `name` | string | yes | Display name shown in the dashboard. |
| `enabled` | boolean | no (default `true`) | When `false`, the feed is not polled. |
| `sound_file` | string or null | no (default `null`) | Absolute path to a WAV file that overrides `sound_map` for this feed. Set to `null` to use the global sound map. |
| `last_poll_time` | string or null | no | ISO 8601 timestamp of the last successful poll. Managed automatically. |
| `has_auth` | boolean | no (default `false`) | Indicates that HTTP Basic credentials for this feed are stored in the OS keyring. Credentials are never written as plaintext. |

---

## `sound_map`

Maps event names to WAV file paths. Relative paths are resolved from the application's bundled `sounds/` directory; absolute paths are used as-is.

| Key | Default value | Description |
|-----|---------------|-------------|
| `new_entry` | `"new_entry.wav"` | Sound played when a new feed entry is detected. |
| `error` | `"error.wav"` | Sound played when a feed poll fails. |

To use a custom sound, provide an absolute path:

```json
"sound_map": {
  "new_entry": "/home/alice/sounds/ding.wav",
  "error": "/home/alice/sounds/buzz.wav"
}
```

---

## `notification_style`

Controls how desktop notifications are displayed.

| Value | Description |
|-------|-------------|
| `"native"` | Uses the OS notification system (recommended on Linux and macOS). |
| `"custom"` | Shows an in-app dialog instead of an OS notification (default on Windows). |

---

## Full example

```json
{
  "poll_interval_secs": 300,
  "notification_style": "native",
  "sound_map": {
    "new_entry": "new_entry.wav",
    "error": "error.wav"
  },
  "feeds": [
    {
      "url": "https://example.com/feed.xml",
      "name": "Example Blog",
      "enabled": true,
      "sound_file": null,
      "last_poll_time": "2024-01-15T12:00:00+00:00",
      "has_auth": false
    },
    {
      "url": "https://private.example.com/feed.xml",
      "name": "Private Feed",
      "enabled": true,
      "sound_file": "/home/alice/sounds/ping.wav",
      "last_poll_time": null,
      "has_auth": true
    }
  ]
}
```
