# Mattermost Bot plugin

This plugin is used to display SnoozeWeb alerts in Mattermost using a chatbot. Users can also partially manage these alerts directly from the chat.

# Installation

```console
$ sudo /opt/snooze/bin/pip install git+https://github.com/snoozeweb/snooze_plugins.git#subdirectory=output/mattermost
$ sudo tee <<SERVICE /etc/systemd/system/snooze-mattermostbot.service
[Unit]
Description=Snooze mattermostbot output plugin
After=network.service

[Service]
User=snooze
ExecStart=/opt/snooze/bin/snooze-mattermostbot
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

$ sudo systemctl daemon-reload
$ sudo systemctl enable snooze-mattermostbot
$ sudo systemctl start snooze-mattermostbot
```

# Prerequisites

* [Snooze Client](https://github.com/snoozeweb/snooze_client): For Snooze Mattermost daemon to use Snooze Server API
* [Mattermost Bot](https://developers.mattermost.com/integrate/admin-guide/admin-bot-accounts/): Mattermost Bot configuration
* [Allow Untrusted Internal Connections](https://docs.mattermost.com/configure/configuration-settings.html#allow-untrusted-internal-connections-to): In Mattermost, set to the daemon IP
* Snooze Action (webhook): Communication between Snooze Server and Snooze Mattermost daemon. See below

## Create Action

In SnoozeWeb, go to the _Actions_ tab then click on **New**

Configuration hints:
* In _Action_, select `Call a webhook`
* In _URL_, put the alert enpoint of the plugin's daemon (if the daemon runs on the same server as Snooze-server: http://localhost:5202/alert)
* In _Payload_, put `{"channels": ["********"], "alert": {{ __self__  | tojson() }} }`
  * Replace `********` with Mattermost Channel ID
* Check `Inject Response`
* Check `Batch` if you want multiple alerts to be grouped in the same thread

## Create Notification

In SnoozeWeb, go to the _Notifications_ tab then click on **New** or **Edit** an existing notification
In _Actions_, select the one you just created

# Configuration

This plugin's configuration is in the following YAML file: `/etc/snooze/mattermostbot.yaml` (`/etc/snooze` can be overridden by the environment variable `SNOOZE_MATTERMOSTBOT_PATH`)

* `mattermost_url` (String, defaults to `http://localhost`): Mattermost URL
* `mattermost_port` (Integer, defaults to `8065`): Mattermost port
* `bot_token` (String, **required**): Mattermost bot token
* `ssl_verify` (Boolean defaults to `false`): Use SSL verification between the daemon and Mattermost
* `listening_address` (String, defaults to `'0.0.0.0'`): Address to listen to
* `listening_port` (Integer, defaults to `5202`): Port to listen to. If lower than 1024, need to run the process as root
* `snooze_url` (String, defaults to `'http://localhost:5200'`): URL to Snooze Web UI
* `date_format` (String, defaults to `'%a, %b %d, %Y at %I:%M %p'`): Date format
* `message_limit` (Integer, defaults to `10`): Maximum number of alerts to explicitly show in the same thread
* `snooze_limit` (Integer, defaults to `message_limit` value): Maximum number of alerts that can be snoozed at the same time without using an explicit condition
* `bot_name` (String, defaults to `'Bot'`): Mattermost Bot name
* `debug` (Boolean, defaults to `false`): Show debug logs
