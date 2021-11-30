# Snooze syslog plugin

The syslog plugin listen in UDP and TCP, and can detect and parse the following syslog format:
* [RFC 3164](https://datatracker.ietf.org/doc/html/rfc3164)
* [RFC 5424](https://datatracker.ietf.org/doc/html/rfc5424)
* Cisco syslog format
* Rsyslog's [`RSYSLOG_ForwardFormat`](https://www.rsyslog.com/doc/v8-stable/configuration/templates.html#reserved-template-names)

# Installation

```console
$ sudo /opt/snooze/bin/pip install git+https://github.com/snoozeweb/snooze_plugins.git#subdirectory=input/syslog
$ sudo tee <<SERVICE >/etc/systemd/system/snooze-syslog.service
[Unit]
Description=Snooze syslog input plugin
After=network.service

[Service]
User=snooze
ExecStart=/opt/snooze/bin/snooze-syslog
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

$ sudo systemctl daemon-reload
$ sudo systemctl enable snooze-syslog
$ sudo systemctl start snooze-syslog
```

> Make sure to configure the `server` in `/etc/snooze/client.yaml` and set it to your snooze
> server URI, as it is mandatory for `snooze-syslog` to work.

# Features

* The plugin listen on both TCP and UDP.
* The plugin can detect and parse several formats (see [Formats](#Formats))

# Formats

The following log formats are detected and supported by the plugin.

For all formats, the `facility` and `severity` will be calculated from the `pri`,
based on RFC 3164 ([section 4.1.1](https://datatracker.ietf.org/doc/html/rfc3164#section-4.1.1)).

## RFC 3164

Example of input format:
```
<34>Jul 6 22:30:00 myhost01 myapp[9999]: my message
```

Example of parsed output:
```json
{
  "source": "syslog",
  "syslog_type": "rfc3164",
  "pri": 34,
  "facility": "auth",
  "severity": "warn"
  "timestamp": "2021-07-01T22:30:00+09:00",
  "host": "myhost01",
  "process": "myapp",
  "pid": 9999,
  "message": "my message",
  "raw": "<34>Jul 6 22:30:00 myhost01 myapp[9999]: my message"
}
```

> Note that it will fill the year, an information missing in RFC 3164,
> with the current year.

## RFC 5424

Example of input format:
```
<165>1 2021-07-01T22:30:00.123Z myhost01 myapp 9999 ID47 my message
```

Example of parsed output:
```json
{
  "source": "syslog",
  "syslog_type": "rfc5424",
  "pri": 165,
  "facility": "local4",
  "severity": "notice",
  "host": "myhost01",
  "process": "myapp",
  "pid": 9999,
  "msgid": "ID47",
  "message": "my message",
  "raw": "<165>1 2021-07-01T22:30:00.123Z myhost01 myapp 9999 ID47 my message"
}
```

## Cisco

## Rsyslog

Example of input format:
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

The `snooze-syslog` process needs to be restarted after changing the configuration:
```console
$ sudo systemctl restart snooze-syslog
```

