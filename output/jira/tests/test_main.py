import json
import pytest
from unittest.mock import patch, MagicMock

from snooze_jira.jira_client import JiraClient


class TestJiraClient:
    """Tests for the JIRA REST API client wrapper."""

    def setup_method(self):
        self.client = JiraClient(
            base_url='https://test.atlassian.net',
            email='test@example.com',
            api_token='test-token',
        )

    def test_text_to_adf_simple(self):
        result = JiraClient._text_to_adf('Hello world')
        assert result == {
            'type': 'doc',
            'version': 1,
            'content': [{
                'type': 'paragraph',
                'content': [{'type': 'text', 'text': 'Hello world'}],
            }],
        }

    def test_text_to_adf_multiline(self):
        result = JiraClient._text_to_adf('Line 1\nLine 2\nLine 3')
        assert result['type'] == 'doc'
        assert len(result['content']) == 3
        assert result['content'][0]['content'][0]['text'] == 'Line 1'
        assert result['content'][1]['content'][0]['text'] == 'Line 2'
        assert result['content'][2]['content'][0]['text'] == 'Line 3'

    def test_text_to_adf_with_blank_lines(self):
        result = JiraClient._text_to_adf('Before\n\nAfter')
        assert len(result['content']) == 3
        assert result['content'][1]['content'] == []

    def test_build_description_adf(self):
        record = {
            'host': 'web01',
            'source': 'nagios',
            'process': 'httpd',
            'severity': 'critical',
            'timestamp': '2026-02-16T10:00:00+0000',
            'message': 'HTTP service is down',
            'hash': 'abc123',
        }
        result = JiraClient.build_description_adf(record, 'https://snooze.example.com')

        assert result['type'] == 'doc'
        assert result['version'] == 1

        # Check heading
        assert result['content'][0]['type'] == 'heading'
        assert result['content'][0]['content'][0]['text'] == 'Snooze Alert'

        # Check fields are present
        all_text = json.dumps(result)
        assert 'web01' in all_text
        assert 'nagios' in all_text
        assert 'httpd' in all_text
        assert 'critical' in all_text
        assert 'HTTP service is down' in all_text

        # Check Snooze link
        assert 'snooze.example.com' in all_text
        assert 'abc123' in all_text

    def test_build_description_adf_no_url(self):
        record = {
            'host': 'web01',
            'source': 'nagios',
            'process': 'httpd',
            'severity': 'critical',
            'message': 'Test message',
        }
        result = JiraClient.build_description_adf(record, '')
        all_text = json.dumps(result)
        assert 'View in Snooze' not in all_text

    def test_build_description_adf_missing_fields(self):
        record = {}
        result = JiraClient.build_description_adf(record)
        all_text = json.dumps(result)
        assert 'Unknown' in all_text

    @patch.object(JiraClient, '_request')
    def test_create_issue(self, mock_request):
        mock_request.return_value = {'id': '10001', 'key': 'OPS-42', 'self': 'https://test.atlassian.net/rest/api/3/issue/10001'}
        result = self.client.create_issue(
            project_key='OPS',
            issue_type='Task',
            summary='Test issue',
            description_adf=JiraClient._text_to_adf('Test description'),
            priority='High',
            labels=['snooze'],
        )
        assert result['key'] == 'OPS-42'
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0] == ('POST', '/issue')
        payload = call_args[1]['json']
        assert payload['fields']['project']['key'] == 'OPS'
        assert payload['fields']['issuetype']['name'] == 'Task'
        assert payload['fields']['summary'] == 'Test issue'
        assert payload['fields']['priority']['name'] == 'High'
        assert payload['fields']['labels'] == ['snooze']

    @patch.object(JiraClient, '_request')
    def test_create_issue_with_extra_fields(self, mock_request):
        mock_request.return_value = {'id': '10002', 'key': 'OPS-43'}
        extra = {'components': [{'name': 'Infrastructure'}]}
        self.client.create_issue(
            project_key='OPS',
            issue_type='Bug',
            summary='Bug report',
            description_adf=JiraClient._text_to_adf('desc'),
            extra_fields=extra,
        )
        payload = mock_request.call_args[1]['json']
        assert payload['fields']['components'] == [{'name': 'Infrastructure'}]

    @patch.object(JiraClient, '_request')
    def test_add_comment(self, mock_request):
        mock_request.return_value = {'id': '100'}
        self.client.add_comment('OPS-42', 'This is a comment')
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0] == ('POST', '/issue/OPS-42/comment')
        body = call_args[1]['json']['body']
        assert body['type'] == 'doc'
        assert body['content'][0]['content'][0]['text'] == 'This is a comment'

    @patch.object(JiraClient, '_request')
    def test_transition_issue(self, mock_request):
        mock_request.return_value = {}
        self.client.transition_issue('OPS-42', '5', comment='Fixed')
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0] == ('POST', '/issue/OPS-42/transitions')
        payload = call_args[1]['json']
        assert payload['transition']['id'] == '5'
        assert 'comment' in payload['update']

    @patch.object(JiraClient, '_request')
    def test_transition_issue_no_comment(self, mock_request):
        mock_request.return_value = {}
        self.client.transition_issue('OPS-42', '5')
        payload = mock_request.call_args[1]['json']
        assert 'update' not in payload

    @patch.object(JiraClient, '_request')
    def test_get_issue(self, mock_request):
        mock_request.return_value = {'key': 'OPS-42', 'fields': {'summary': 'Test'}}
        result = self.client.get_issue('OPS-42')
        assert result['key'] == 'OPS-42'
        mock_request.assert_called_once_with('GET', '/issue/OPS-42')

    @patch.object(JiraClient, '_request')
    def test_get_transitions(self, mock_request):
        mock_request.return_value = {
            'transitions': [
                {'id': '11', 'name': 'To Do', 'to': {'name': 'To Do'}},
                {'id': '21', 'name': 'In Progress', 'to': {'name': 'In Progress'}},
            ]
        }
        result = self.client.get_transitions('OPS-42')
        assert len(result) == 2
        assert result[0]['id'] == '11'
        mock_request.assert_called_once_with('GET', '/issue/OPS-42/transitions')


class TestJiraPlugin:
    """Tests for the main JiraPlugin logic."""

    def _make_plugin(self, config=None):
        from snooze_jira.main import JiraPlugin
        default_config = {
            'jira_url': 'https://test.atlassian.net',
            'jira_email': 'test@example.com',
            'jira_api_token': 'test-token',
            'project_key': 'OPS',
            'issue_type': 'Task',
            'priority': 'Medium',
            'labels': ['snooze'],
            'snooze_url': 'https://snooze.example.com',
            'summary_template': '[${severity}] ${host} - ${message}',
        }
        if config:
            default_config.update(config)
        with patch('snooze_jira.main.Snooze'):
            plugin = JiraPlugin(default_config)
        return plugin

    def test_format_summary(self):
        plugin = self._make_plugin()
        record = {
            'severity': 'critical',
            'host': 'web01',
            'message': 'HTTP service is down',
        }
        summary = plugin._format_summary(record)
        assert summary == '[critical] web01 - HTTP service is down'

    def test_format_summary_missing_fields(self):
        plugin = self._make_plugin()
        record = {}
        summary = plugin._format_summary(record)
        assert 'Unknown' in summary

    def test_format_summary_truncation(self):
        plugin = self._make_plugin()
        record = {
            'severity': 'critical',
            'host': 'web01',
            'message': 'A' * 300,
        }
        summary = plugin._format_summary(record)
        assert len(summary) <= 255

    def test_format_summary_custom_template(self):
        plugin = self._make_plugin({'summary_template': '${host}: ${severity}'})
        record = {'host': 'db01', 'severity': 'warning'}
        summary = plugin._format_summary(record)
        assert summary == 'db01: warning'

    def test_find_existing_issue_found(self):
        plugin = self._make_plugin()
        record = {
            'snooze_webhook_responses': [{
                'action_name': 'jira_action',
                'content': {'issue_key': 'OPS-42'},
            }],
        }
        result = plugin._find_existing_issue(record, 'jira_action')
        assert result == 'OPS-42'

    def test_find_existing_issue_not_found(self):
        plugin = self._make_plugin()
        record = {
            'snooze_webhook_responses': [{
                'action_name': 'other_action',
                'content': {'issue_key': 'OPS-42'},
            }],
        }
        result = plugin._find_existing_issue(record, 'jira_action')
        assert result is None

    def test_find_existing_issue_no_responses(self):
        plugin = self._make_plugin()
        record = {}
        result = plugin._find_existing_issue(record, 'jira_action')
        assert result is None

    def test_build_comment(self):
        plugin = self._make_plugin()
        record = {
            'timestamp': '2026-02-16T10:00:00+0000',
            'host': 'web01',
            'severity': 'critical',
            'message': 'Service down',
        }
        comment = plugin._build_comment(record, message='Please check')
        assert 'Re-escalation' in comment
        assert 'web01' in comment
        assert 'critical' in comment
        assert 'Service down' in comment
        assert 'Please check' in comment

    def test_build_comment_with_notification_from(self):
        plugin = self._make_plugin()
        record = {'host': 'web01', 'severity': 'critical', 'message': 'down'}
        notification_from = {'name': 'AlertManager', 'message': 'Auto-escalated'}
        comment = plugin._build_comment(record, notification_from=notification_from)
        assert 'AlertManager' in comment
        assert 'Auto-escalated' in comment

    @patch.object(JiraClient, 'create_issue')
    def test_process_records_new_issue(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10001', 'key': 'OPS-42'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'abc123',
                'host': 'web01',
                'source': 'nagios',
                'process': 'httpd',
                'severity': 'critical',
                'message': 'HTTP down',
            },
        }]

        result = plugin.process_records(req, medias)
        assert 'abc123' in result
        assert result['abc123']['issue_key'] == 'OPS-42'
        mock_create.assert_called_once()

    @patch.object(JiraClient, 'add_comment')
    def test_process_records_existing_issue(self, mock_comment):
        plugin = self._make_plugin()
        mock_comment.return_value = {'id': '200'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'abc123',
                'host': 'web01',
                'severity': 'critical',
                'message': 'HTTP down again',
                'snooze_webhook_responses': [{
                    'action_name': 'jira_action',
                    'content': {'issue_key': 'OPS-42'},
                }],
            },
        }]

        result = plugin.process_records(req, medias)
        assert result['abc123']['issue_key'] == 'OPS-42'
        mock_comment.assert_called_once()

    @patch.object(JiraClient, 'create_issue')
    def test_process_records_custom_project(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10002', 'key': 'INFRA-1'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'project_key': 'INFRA',
            'issue_type': 'Bug',
            'priority': 'High',
            'alert': {
                'hash': 'def456',
                'host': 'db01',
                'severity': 'warning',
                'message': 'Disk space low',
            },
        }]

        result = plugin.process_records(req, medias)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['project_key'] == 'INFRA'
        assert call_kwargs['issue_type'] == 'Bug'
        assert call_kwargs['priority'] == 'High'

    @patch.object(JiraClient, 'create_issue')
    def test_priority_mapping_critical(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10003', 'key': 'OPS-50'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'prio1',
                'host': 'web01',
                'severity': 'critical',
                'message': 'Down',
            },
        }]

        plugin.process_records(req, medias)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['priority'] == 'Highest'

    @patch.object(JiraClient, 'create_issue')
    def test_priority_mapping_info(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10004', 'key': 'OPS-51'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'prio2',
                'host': 'web01',
                'severity': 'info',
                'message': 'Informational',
            },
        }]

        plugin.process_records(req, medias)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['priority'] == 'Lowest'

    @patch.object(JiraClient, 'create_issue')
    def test_priority_mapping_unknown_severity_uses_default(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10005', 'key': 'OPS-52'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'prio3',
                'host': 'web01',
                'severity': 'unknown_level',
                'message': 'Something',
            },
        }]

        plugin.process_records(req, medias)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['priority'] == 'Medium'  # default_priority

    @patch.object(JiraClient, 'create_issue')
    def test_priority_payload_override_beats_mapping(self, mock_create):
        plugin = self._make_plugin()
        mock_create.return_value = {'id': '10006', 'key': 'OPS-53'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'priority': 'Low',
            'alert': {
                'hash': 'prio4',
                'host': 'web01',
                'severity': 'critical',
                'message': 'Override',
            },
        }]

        plugin.process_records(req, medias)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['priority'] == 'Low'  # payload override, not 'Highest'

    @patch.object(JiraClient, 'transition_issue')
    @patch.object(JiraClient, 'get_transitions')
    @patch.object(JiraClient, 'get_issue')
    @patch.object(JiraClient, 'add_comment')
    def test_reopen_closed_issue(self, mock_comment, mock_get_issue, mock_get_trans, mock_transition):
        plugin = self._make_plugin({'reopen_closed': True, 'reopen_status_name': 'To Do'})
        mock_comment.return_value = {'id': '200'}
        mock_get_issue.return_value = {
            'fields': {
                'status': {
                    'name': 'Done',
                    'statusCategory': {'key': 'done'},
                },
            },
        }
        mock_get_trans.return_value = [
            {'id': '11', 'name': 'Reopen', 'to': {'name': 'To Do', 'statusCategory': {'key': 'new'}}},
        ]
        mock_transition.return_value = {}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'reopen1',
                'host': 'web01',
                'severity': 'critical',
                'message': 'Back again',
                'snooze_webhook_responses': [{
                    'action_name': 'jira_action',
                    'content': {'issue_key': 'OPS-42'},
                }],
            },
        }]

        result = plugin.process_records(req, medias)
        mock_comment.assert_called_once()
        mock_get_issue.assert_called_once_with('OPS-42')
        mock_transition.assert_called_once_with('OPS-42', '11', comment='Reopened by Snooze due to re-escalation')

    @patch.object(JiraClient, 'get_issue')
    @patch.object(JiraClient, 'add_comment')
    def test_no_reopen_when_disabled(self, mock_comment, mock_get_issue):
        plugin = self._make_plugin({'reopen_closed': False})
        mock_comment.return_value = {'id': '200'}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'reopen2',
                'host': 'web01',
                'severity': 'critical',
                'message': 'Still down',
                'snooze_webhook_responses': [{
                    'action_name': 'jira_action',
                    'content': {'issue_key': 'OPS-42'},
                }],
            },
        }]

        plugin.process_records(req, medias)
        mock_comment.assert_called_once()
        mock_get_issue.assert_not_called()  # Should not even check issue status

    @patch.object(JiraClient, 'transition_issue')
    @patch.object(JiraClient, 'get_transitions')
    @patch.object(JiraClient, 'get_issue')
    @patch.object(JiraClient, 'add_comment')
    def test_reopen_fallback_transition(self, mock_comment, mock_get_issue, mock_get_trans, mock_transition):
        """When the configured reopen_status_name doesn't match, fall back to any non-done transition."""
        plugin = self._make_plugin({'reopen_closed': True, 'reopen_status_name': 'Open'})
        mock_comment.return_value = {'id': '200'}
        mock_get_issue.return_value = {
            'fields': {
                'status': {
                    'name': 'Done',
                    'statusCategory': {'key': 'done'},
                },
            },
        }
        mock_get_trans.return_value = [
            {'id': '21', 'name': 'In Progress', 'to': {'name': 'In Progress', 'statusCategory': {'key': 'indeterminate'}}},
        ]
        mock_transition.return_value = {}

        req = MagicMock()
        req.params = {'snooze_action_name': 'jira_action'}

        medias = [{
            'alert': {
                'hash': 'reopen3',
                'host': 'web01',
                'severity': 'warning',
                'message': 'Back',
                'snooze_webhook_responses': [{
                    'action_name': 'jira_action',
                    'content': {'issue_key': 'OPS-99'},
                }],
            },
        }]

        plugin.process_records(req, medias)
        # Should fall back to 'In Progress' transition
        mock_transition.assert_called_once_with('OPS-99', '21', comment='Reopened by Snooze due to re-escalation')
