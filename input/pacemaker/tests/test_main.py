from snooze_pacemaker.main import make_record

class TestPacemaker1x:
    def test_resource(self):
        environment = {
            'CRM_alert_kind': 'resource',
            'CRM_alert_version': '1.1.23',
            'CRM_alert_recipient': 'https://snooze.example.com:5200',
            'CRM_alert_node_sequence': '34',
            'CRM_alert_timestamp': '2021-08-23T13:50:04',
            'CRM_alert_node': 'myhost01',
            'CRM_alert_rsc': 'myresource',
            'CRM_alert_desc': 'unknown error',
            'CRM_alert_task': 'start',
            'CRM_alert_rc': '1',
            'CRM_alert_interval': '0',
            'CRM_alert_target_rc': '0',
            'CRM_alert_status': '0',
        }
        record = make_record(environment)
        assert record
        assert record['host'] == 'myhost01'
        assert record['timestamp'] == '2021-08-23T13:50:04+09:00'
        assert record['process'] == 'resource'
        assert record['message'] == "Resource operation 'start' for 'myresource': unknown error"
