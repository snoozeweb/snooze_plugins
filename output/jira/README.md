# JIRA Output Plugin

This plugin creates JIRA tickets from SnoozeWeb alerts. When an alert is triggered, the plugin creates a new JIRA issue with the alert details. On re-escalation, it adds a comment to the existing ticket instead of creating a duplicate.

## Installation

```console
$ sudo /opt/snooze/bin/pip install git+https://github.com/snoozeweb/snooze_plugins.git#subdirectory=output/jira
$ sudo tee <<SERVICE /etc/systemd/system/snooze-jira.service
[Unit]
Description=Snooze JIRA output plugin
After=network.service

[Service]
User=snooze
ExecStart=/opt/snooze/bin/snooze-jira
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

$ sudo systemctl daemon-reload
$ sudo systemctl enable snooze-jira
$ sudo systemctl start snooze-jira
```

## Prerequisites

* [Snooze Client](https://github.com/snoozeweb/snooze_client): For the Snooze JIRA daemon to use Snooze Server API
* [JIRA Cloud API Token](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/): Create an API token in your Atlassian account settings
* Snooze Action (webhook): Communication between Snooze Server and the Snooze JIRA daemon. See below

## Create Action

In SnoozeWeb, go to the _Actions_ tab then click on **New**

Configuration hints:
* In _Action_, select `Call a webhook`
* In _URL_, put the alert endpoint of the plugin's daemon (if the daemon runs on the same server as Snooze-server: `http://localhost:5203/alert`)
* In _Payload_, put:
  ```json
  {"project_key": "OPS", "alert": {{ __self__ | tojson() }}}
  ```
  * Replace `OPS` with your JIRA project key
  * You can optionally add `"message": "Custom message"` to include extra context
  * You can override per-alert: `"issue_type": "Bug"`, `"priority": "High"`, `"labels": ["critical", "snooze"]`
* Check `Inject Response`
* Check `Batch` if you want multiple alerts to create separate tickets

### Full payload example

```json
{
  "project_key": "OPS",
  "issue_type": "Bug",
  "priority": "High",
  "labels": ["snooze", "production"],
  "alert": {{ __self__ | tojson() }},
  "message": "Requires immediate attention"
}
```

## Create Notification

In SnoozeWeb, go to the _Notifications_ tab then click on **New** or **Edit** an existing notification.
In _Actions_, select the one you just created.

## Configuration

This plugin's configuration is in the following YAML file: `/etc/snooze/jira.yaml` (`/etc/snooze` can be overridden by the environment variable `SNOOZE_JIRA_PATH`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `jira_url` | String | **required** | JIRA Cloud base URL (e.g. `https://mycompany.atlassian.net`) |
| `jira_email` | String | **required** | Email address for JIRA API authentication |
| `jira_api_token` | String | **required** | JIRA API token (create at [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| `project_key` | String | **required** | Default JIRA project key (e.g. `OPS`) |
| `issue_type` | String | `Task` | Default issue type (e.g. `Task`, `Bug`, `Story`) |
| `priority` | String | `Medium` | Default issue priority (e.g. `Highest`, `High`, `Medium`, `Low`, `Lowest`) |
| `labels` | List | `["snooze"]` | Default labels to add to created tickets |
| `summary_template` | String | `[${severity}] ${host} - ${message}` | Template for issue summary. Available variables: `${severity}`, `${host}`, `${source}`, `${process}`, `${message}`, `${timestamp}` |
| `extra_fields` | Dict | `{}` | Additional JIRA fields to set on issue creation (e.g. `{"components": [{"name": "Infrastructure"}]}`) |
| `ssl_verify` | Boolean | `true` | Use SSL verification for JIRA API requests |
| `listening_address` | String | `0.0.0.0` | Address to listen to |
| `listening_port` | Integer | `5203` | Port to listen to |
| `snooze_url` | String | `http://localhost:5200` | URL to Snooze Web UI (used for links in JIRA descriptions) |
| `message_limit` | Integer | `10` | Maximum number of alerts to process per webhook call |
| `debug` | Boolean | `false` | Show debug logs |

### Example configuration

```yaml
jira_url: https://mycompany.atlassian.net
jira_email: bot@mycompany.com
jira_api_token: ATATT3xFfGF0...
project_key: OPS
issue_type: Task
priority: Medium
labels:
  - snooze
  - monitoring
summary_template: "[${severity}] ${host} - ${message}"
ssl_verify: true
listening_address: 0.0.0.0
listening_port: 5203
snooze_url: https://snooze.mycompany.com
message_limit: 10
debug: false
```

## How It Works

1. **Alert received**: SnoozeWeb sends a webhook POST to `/alert` on the daemon
2. **New alert**: A new JIRA issue is created with the alert details (host, source, severity, message, etc.)
3. **Re-escalation**: If the alert was already sent previously (tracked via `Inject Response`), a comment is added to the existing JIRA ticket instead of creating a duplicate
4. **Response injection**: The JIRA issue key is returned to SnoozeWeb and stored in the record's `snooze_webhook_responses`, enabling deduplication on subsequent triggers

## JIRA API Authentication

This plugin uses [Basic authentication](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/) with your email and an API token. To create an API token:

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a descriptive label (e.g. "Snooze Bot")
4. Copy the token and add it to your `jira.yaml` configuration
