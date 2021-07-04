# Snooze syslog plugin

# Features

* The plugin listen on both TCP and UDP.
* The plugin can detect and parse several formats (see [Formats](#Formats))

# Formats

The following log formats are detected and supported by the plugin.

## RFC 3164

## RFC 5424

## Cisco

## Rsyslog

Example log:
```
<27>2021-07-01T22:30:00 myhost01 myapp[9999]: my message
```

Example of parsed output:
```json
{
  "source": "syslog",
  "syslog_type": "rsyslog",
  "pri": 27,
  "severity": "err",
  "facility": "daemon",
  "timestamp": "2021-07-01T22:30:00+00:00",
  "host": "myhost01",
  "process": "myapp"
  "message": "my message",
  "raw": "<27>2021-07-01T22:30:00 myhost01 myapp[9999]: my message"
}
```

# Configuration

Configuration is done in a YAML file at `/etc/snooze/syslog.yaml` (or the value of the `SNOOZE_SYSLOG_CONFIG` environment variable).

Example configuration can be found at [examples/syslog.yaml](./examples/syslog.yaml).

General options:
* `listening_address` (String, defaults to `0.0.0.0`): Address to listen to.
* `listening_port` (Integer, defaults to `1514`): Port to listen to. Please note than when choosing a port
lower than 1024 (like 514 for instance), you will need to run the process as root.
* `snooze_server` (String): URI of the snooze server to send records to. If not specified, will default to the
value in `/etc/snooze/client.yaml`.

Worker options:
* `parse_workers` (Integer, defaults to `4`): Number of threads to use for parsing.
* `send_workers` (Integer, defaults to `4`): Number of threads to use for sending to snooze server.

TLS options:
* `ssl` (Boolean, defaults to `false`): Turn on TLS for syslog.
* `certfile` (String): When `ssl` is turned on, the absolute path to the certificate file (in PEM format).
* `keyfile` (String): When `ssl` is turned on, the absolute path to the key file (in PEM format).
