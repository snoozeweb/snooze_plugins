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
  * You can override per-alert: `"issue_type": "Bug"`, `"priority": "High"`, `"labels": ["critical", "snooze"]`, `"assignee": "<account_id_or_email>"`, `"reporter": "<account_id_or_email>"`, `"custom_fields": {"customfield_10100": {"value": "Networking"}}`
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
| `priority` | String | `Medium` | Default issue priority, used when severity is not found in `priority_mapping` |
| `priority_mapping` | Dict | see below | Maps Snooze alert severity to JIRA priority name |
| `labels` | List | `["snooze"]` | Default labels to add to created tickets |
| `summary_template` | String | `[${severity}] ${host} - ${message}` | Template for issue summary. Available variables: `${severity}`, `${host}`, `${source}`, `${process}`, `${message}`, `${timestamp}` |
| `extra_fields` | Dict | `{}` | Additional JIRA fields to set on issue creation (e.g. `{"components": [{"name": "Infrastructure"}]}`) |
| `assignee` | String | | Default assignee — JIRA account ID (e.g. `5b109f2e9729b51b54dc274d`) or email address (e.g. `user@example.com`). Can be overridden per-alert in payload |
| `reporter` | String | | Default reporter — JIRA account ID or email address. Can be overridden per-alert in payload |
| `custom_fields` | Dict | `{}` | Arbitrary JIRA custom fields to set on issue creation. Values are passed through as-is to the JIRA API. See examples below |
| `reopen_closed` | Boolean | `false` | When true, re-escalation on a closed/done JIRA ticket will reopen it |
| `reopen_status_name` | String | `To Do` | Target status name when reopening a closed ticket (e.g. `To Do`, `Open`, `Backlog`) |
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
priority_mapping:
  critical: "Highest"
  major: "High"
  warning: "Medium"
  minor: "Low"
  info: "Lowest"
labels:
  - snooze
  - monitoring
summary_template: "[${severity}] ${host} - ${message}"
assignee: "5b109f2e9729b51b54dc274d"    # JIRA account ID or email
reporter: "bot@mycompany.com"              # email-based reporter
custom_fields:
  customfield_10100:
    value: "Infrastructure"
  customfield_10718:
    - id: "11688"
      value: "DevOps 🟣"
reopen_closed: true
reopen_status_name: "To Do"
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
4. **Reopen closed tickets** (optional): If `reopen_closed: true` is set and the existing ticket is in a done/closed status, the plugin will automatically transition it back to the configured `reopen_status_name` (default: `To Do`)
5. **Response injection**: The JIRA issue key is returned to SnoozeWeb and stored in the record's `snooze_webhook_responses`, enabling deduplication on subsequent triggers

## Priority Mapping

The `priority_mapping` configuration maps Snooze alert severities to JIRA priority names. When a new ticket is created, the plugin looks up the alert's `severity` field in this mapping to determine the JIRA priority.

**Default mapping:**

| Snooze Severity | JIRA Priority |
|---|---|
| `critical` | `Highest` |
| `major` | `High` |
| `warning` | `Medium` |
| `minor` | `Low` |
| `info` | `Lowest` |

Priority resolution order:
1. Explicit `priority` in webhook payload (per-alert override)
2. `priority_mapping` based on alert severity
3. Default `priority` from configuration

## JIRA API Authentication

This plugin uses [Basic authentication](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/) with your email and an API token. To create an API token:

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a descriptive label (e.g. "Snooze Bot")
4. Copy the token and add it to your `jira.yaml` configuration

## Custom Fields

The `custom_fields` configuration supports arbitrary JIRA custom fields. Values are passed through directly to the JIRA REST API, so any structure supported by JIRA can be used.

**Simple select field:**
```yaml
custom_fields:
  customfield_10100:
    value: "Infrastructure"
```

**Array of objects (e.g. multi-select or cascading field):**
```yaml
custom_fields:
  customfield_10718:
    - id: "11688"
      value: "DevOps 🟣"
    - id: "11689"
      value: "SRE 🔵"
```

**Multiple custom fields:**
```yaml
custom_fields:
  customfield_10100:
    value: "Infrastructure"
  customfield_10200: "plain string value"
  customfield_10718:
    - id: "11688"
      value: "DevOps 🟣"
```

Custom fields can also be overridden per-alert in the webhook payload:
```json
{
  "project_key": "OPS",
  "custom_fields": {
    "customfield_10100": {"value": "Networking"}
  },
  "alert": {{ __self__ | tojson() }}
}
```

Payload custom fields are merged on top of config defaults (payload wins for same field ID).

## Assignee and Reporter

The `assignee` and `reporter` fields support both JIRA account IDs and email addresses. The plugin auto-detects the format:

- **Account ID** (no `@`): `assignee: "5b109f2e9729b51b54dc274d"` → `{"id": "5b109f2e9729b51b54dc274d"}`
- **Email address** (contains `@`): `assignee: "john@example.com"` → `{"emailAddress": "john@example.com"}`

Both can be overridden per-alert in the webhook payload.
