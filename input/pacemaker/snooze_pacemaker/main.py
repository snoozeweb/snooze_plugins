'''Helper to send alerts from pacemaker'''

import os
import re

import dateutil.parser

from datetime import datetime
from subprocess import Popen, TimeoutExpired, CalledProcessError

from snooze_client import Snooze

# As described by https://clusterlabs.org/pacemaker/doc/deprecated/en-US/Pacemaker/2.0/html-single/Pacemaker_Explained/index.html#_alert_instance_attributes
KEYS = [
    'alert_kind',
    'alert_version',
    'alert_node_sequence',
    'alert_timestamp',
    'alert_timestamp_epoch',
    'alert_timestamp_usec',
    'alert_node',
    'alert_desc',
    'alert_nodeid',
    'alert_task',
    'alert_rc',
    'alert_rsc',
    'alert_interval',
    'alert_target_rc',
    'alert_status',
    'alert_exec_time',
    'alert_attribute_name',
    'alert_attribute_value',
]

SEVERITY_KEYWORDS = {
    'ok': 'ok',
    'unknown': 'unknown',
    'not running': 'err',
    'cancelled': 'err',
}

def get_cluster_name():
    '''Execute a pacemaker command to get the cluster name'''
    try:
        proc = Popen(['crm_attribute', '--query', '-n', 'cluster-name', '-q'], shell=True)
        stdout, _ = proc.communicate(timeout=3)
        if stdout:
            lines = stdout.split('\n')
            return lines[-1]
        else:
            return None
    except [TimeoutExpired, CalledProcessError]:
        return None

def guess_severity(pacemaker):
    '''Guess the severity based on the input dict'''
    for (regex, keyword) in SEVERITY_KEYWORDS.items():
        if re.search(regex, pacemaker['alert_desc'], re.I):
            return keyword
    else:
        return 'err'

def make_record(environment):
    '''
    Create a snooze record based on the pacemaker environment variables
    '''
    pacemaker = {}
    record = {}
    record['pacemaker'] = pacemaker
    record['source'] = 'pacemaker'

    for key in KEYS:
        value = environment.get("CRM_"+key)
        if value:
            pacemaker[key] = value

    cluster_name = get_cluster_name()
    if cluster_name:
        pacemaker['cluster_name'] = cluster_name

    if 'alert_timestamp_epoch' in pacemaker: # Pacemaker 2.0
        timestamp = pacemaker['alert_timestamp_epoch']
        pacemaker['alert_timestamp_epoch'] = int(timestamp)
        record['timestamp'] = datetime.fromtimestamp(timestamp).astimezone().isoformat()
    elif 'alert_timestamp' in pacemaker: # Pacemaker 1.1
        timestamp = dateutil.parser.parse(pacemaker['alert_timestamp'])
        record['timestamp'] = timestamp.astimezone().isoformat()

    if 'alert_node' in pacemaker:
        record['host'] = pacemaker['alert_node']
    if 'alert_kind' in pacemaker:
        record['process'] = pacemaker['alert_kind']
    else:
        record['process'] = 'pacemaker'

    if pacemaker['alert_kind'] == 'node':
        message = "Node '{}' is now '{}'".format(pacemaker['alert_node'], pacemaker['alert_desc'])
    elif pacemaker['alert_kind'] == 'fencing':
        message = "Fencing {}".format(pacemaker['alert_desc'])
    elif pacemaker['alert_kind'] == 'resource':
        message = "Resource operation '{}' for '{}': {}".format(
            pacemaker['alert_task'],
            pacemaker['alert_rsc'],
            pacemaker['alert_desc']
        )
    else:
        message = pacemaker['alert_desc']

    record['message'] = message
    record['severity'] = guess_severity(pacemaker)

    return record

def alert():
    '''Send an alert to pacemaker'''
    record = make_record(os.environ)

    url = os.environ['CRM_alert_recipient']
    server = Snooze(url)

    server.alert_with_defaults(record)

if __name__ == '__main__':
    alert()
