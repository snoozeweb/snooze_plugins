'''Helper to send alerts from pacemaker'''

import os

import dateutil

from datetime import datetime

from snooze_client import Snooze

# As described by https://clusterlabs.org/pacemaker/doc/deprecated/en-US/Pacemaker/2.0/html-single/Pacemaker_Explained/index.html#_alert_instance_attributes
KEYS = [
    'alert_kind',
    'alert_version',
    'alert_recipient',
    'alert_node_sequence',
    'alert_timestamp',
    'alert_timestamp_epoch',
    'alert_timestamp_usec',
    'alert_node',
    'alert_desc',
    'alert_nodeid',
    'alert_task',
    'alert_rc',
    'alert_rcs',
    'alert_interval',
    'alert_target_rc',
    'alert_status',
    'alert_exec_time',
    'alert_attribute_name',
    'alert_attribute_value',
]

def alert():
    '''Send an alert to pacemaker'''
    pacemaker = {}
    record = {}
    record['pacemaker'] = pacemaker
    record['source'] = 'pacemaker'

    for key in KEYS:
        value = os.environ.get("CRM_"+key)
        pacemaker[key] = value

    if 'alert_timestamp_epoch' in pacemaker: # Pacemaker 2.0
        timestamp = pacemaker['alert_timestamp_epoch']
        pacemaker['alert_timestamp_epoch'] = int(timestamp)
        record['timestamp'] = datetime.fromtimestamp(timestamp).astimezone().isoformat()
    elif 'alert_timestamp' in pacemaker: # Pacemaker 1.1
        timestamp = dateutil.parser.parse(pacemaker['alert_timestamp'])
        record['timestamp'] = timestamp.astimezone().isoformat()

    if 'alert_node' in pacemaker:
        record['host'] = pacemaker['alert_node']
    if 'alert_desc' in pacemaker:
        record['message'] = pacemaker['alert_desc']
    if 'alert_kind' in pacemaker:
        record['process'] = "pacemaker/{}".format(pacemaker['alert_kind'])

    server = Snooze()
    server.alert_with_defaults(record)

if __name__ == '__main__':
    alert()
