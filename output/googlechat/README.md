# Snooze Google Bot plugin

This plugin was firstly meant to display alerts in Google Chat using a chatbot. Since it partialy wraps snooze server REST API, it can also be used to create/manage Snooze filters

# Installation

```console
$ sudo /opt/snooze/bin/pip install snooze-googlechat
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

# Configuration

Make sure to configure [snooze-client](https://github.com/snoozeweb/snooze_client) beforehand since this plugin relies on it to be able to use snooze-server API
Set up a google chatbot using Pub/Sub as connection settings ([How to create a google chatbot](https://developers.google.com/chat/concepts)) 

This plugin's configuration is in the following YAML file: `/etc/snooze/googlechat.yaml` (can be overridden by the environment variable `SNOOZE_GOOGLE_CHATBOT_CONFIG_FILE`)

General options:

* `subscription_name`\* (String): Google PubSub subscription name used to pull messages
* `service_account_path`\* (String, defaults to `'$HOME/.sa\_secrets.json'`): Fully qualified path of google's service account credentials
* `listening_address` (String, defaults to `'0.0.0.0'`): Address to listen to
* `listening_port` (Integer, defaults to `5201`): Port to listen to. If lower than 1024, need to run the process as root
* `snooze_url` (String, defaults to `'http://localhost:5200'`): URL to Snooze Web UI
* `date_format` (String, defaults to `'%a, %b %d, %Y at %I:%M %p'`): Date format
* `bot_name` (String, defaults to `'Bot'`): Google Bot name
* `debug` (Boolean, defaults to `false`): Show debug logs
