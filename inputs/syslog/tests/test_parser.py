'''Test cases for the syslog format parser'''

from datetime import datetime
from snooze_syslog.parser import *

def test_detect_rsyslog():
    data = b"<27>2021-07-01T22:30:00 myhost01 myapp[9999]: my message"
    records = parse_syslog('192.168.0.1', data)
    record = records[0]
    assert record['syslog_type'] == 'rsyslog'

def test_parse_rsyslog():
    msg = "<27>2021-07-01T22:30:00 myhost01 myapp[9999]: my message"
    record = parse_rsyslog(msg)
    timezone = datetime.now().astimezone().strftime('%z')
    timezone = timezone[:3] + ':' + timezone[3:]
    expected_record = {
        'syslog_type': 'rsyslog',
        'pri': 27,
        'host': 'myhost01',
        'process': 'myapp',
        'pid': 9999,
        'message': 'my message',
        'timestamp': '2021-07-01T22:30:00' + timezone,
    }
    assert record == expected_record

def test_detect_rfc5424():
    data = b'<165>1 2021-07-01T22:30:00.123Z myhost01 myapp 9999 ID47 my message'
    records = parse_syslog('192.168.0.1', data)
    record = records[0]
    assert record['syslog_type'] == 'rfc5424'

def test_parse_rfc5424():
    msg = '<165>1 2021-07-01T22:30:00.123Z myhost01 myapp 9999 ID47 my message'
    record = parse_rfc5424(msg)
    expected_record = {
        'syslog_type': 'rfc5424',
        'pri': 165,
        'host': 'myhost01',
        'process': 'myapp',
        'pid': 9999,
        'msgid': 'ID47',
        'message': 'my message',
        'timestamp': '2021-07-01T22:30:00.123Z',
    }
    assert record == expected_record

def test_rfc5425_struct_parser():
    data = '[exampleSDID@9999 a="1" b="2"][exampleSDID@8888 c="3" d="4"]'
    struct = parse_rfc5424_struct(data)
    expected_struct = {
        'exampleSDID@9999': {'a': '1', 'b': '2'},
        'exampleSDID@8888': {'c': '3', 'd': '4'},
    }
    assert struct == expected_struct

def test_rfc5425_parser_with_struct():
    msg = '<165>1 2021-07-01T22:30:00.123Z myhost01 myapp 9999 ID47 [exampleSDID@9999 a="1" b="2"][exampleSDID@8888 c="3" d="4"] my message'
    record = parse_rfc5424(msg)
    expected_record = {
        'syslog_type': 'rfc5424',
        'pri': 165,
        'host': 'myhost01',
        'process': 'myapp',
        'pid': 9999,
        'msgid': 'ID47',
        'message': 'my message',
        'timestamp': '2021-07-01T22:30:00.123Z',
        'exampleSDID@9999': {'a': '1', 'b': '2'},
        'exampleSDID@8888': {'c': '3', 'd': '4'},
    }
    assert record == expected_record

def test_detect_rfc3164():
    data = b'<34>Jul 6 22:30:00 myhost01 myapp[9999]: my message'
    records = parse_syslog('192.168.0.1', data)
    record = records[0]
    assert record['syslog_type'] == 'rfc3164'

def test_parse_rfc3164():
    msg = '<34>Jul 6 22:30:00 myhost01 myapp[9999]: my message'
    record = parse_rfc3164(msg)
    year = str(datetime.now().year)
    timezone = datetime.now().astimezone().strftime('%z')
    timezone = timezone[:3] + ':' + timezone[3:]
    expected_record = {
        'syslog_type': 'rfc3164',
        'pri': 34,
        'timestamp': year + "-07-06T22:30:00" + timezone,
        'host': 'myhost01',
        'process': 'myapp',
        'pid': 9999,
        'message': 'my message',
    }
    assert record == expected_record
