# Snooze Google Bot plugin

This plugin is used to display SnoozeWeb alerts in Google Chat using a chatbot. Users can also partially manage these alerts directly from the chat.

# Installation

```console
$ sudo /opt/snooze/bin/pip install git+https://github.com/snoozeweb/snooze_plugins.git#subdirectory=output/googlechat
$ sudo tee <<SERVICE /etc/systemd/system/snooze-googlechat.service
[Unit]
Description=Snooze googlechat output plugin
After=network.service

[Service]
User=snooze
ExecStart=/opt/snooze/bin/snooze-googlechat
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

$ sudo systemctl daemon-reload
$ sudo systemctl enable snooze-googlechat
$ sudo systemctl start snooze-googlechat
```

# Prerequisites

* [Snooze Client](https://github.com/snoozeweb/snooze_client): For Snooze Google Chat daemon to use Snooze Server API
* [Google Service Account](doc/01_Service_Account.md): Snooze Google Chat daemon credentials
* [Google Pub/Sub](doc/02_PubSub.md): Communication between Snooze Google Chat daemon and Google Chat Bot
* [Google Chat](doc/03_Chat.md): Google Chat Bot configuration
* [Snooze Action (webhook)](doc/04_Action.md): Communication between Snooze Server and Snooze Google Chat daemon

# Configuration

This plugin's configuration is in the following YAML file: `/etc/snooze/googlechat.yaml` (`/etc/snooze` can be overridden by the environment variable `SNOOZE_GOOGLE_CHATBOT_PATH`)

General options:

* `subscription_name`\* (String, **required**): Google PubSub subscription name used to pull messages
* `service_account_path`\* (String, defaults to `'$HOME/.sa\_secrets.json'`): Fully qualified path of google's service account credentials
* `listening_address` (String, defaults to `'0.0.0.0'`): Address to listen to
* `listening_port` (Integer, defaults to `5201`): Port to listen to. If lower than 1024, need to run the process as root
* `snooze_url` (String, defaults to `'http://localhost:5200'`): URL to Snooze Web UI
* `date_format` (String, defaults to `'%a, %b %d, %Y at %I:%M %p'`): Date format
* `message_limit` (Integer, defaults to `10`): Maximum number of alerts to explicitly show in the same thread
* `snooze_limit` (Integer, defaults to `message_limit` value): Maximum number of alerts that can be snoozed at the same time without using an explicit condition
* `bot_name` (String, defaults to `'Bot'`): Google Bot name
* `use_card` (Boolean, defaults to `false`): Add interactive buttons at the end of each message
* `debug` (Boolean, defaults to `false`): Show debug logs
