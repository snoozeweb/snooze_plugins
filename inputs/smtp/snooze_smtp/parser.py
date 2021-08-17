'''Module for miscellaneous parsers'''

import re
from dateutil.parser import parse

OPT_SPACE = r'[\n\r\s]*'
SPACE = r'[\n\r\s]+'
REGEX_STR = ''.join([
    '(',
    'from', SPACE, r'(?P<from>.*?)', SPACE,
    r'\(', r'(?P<from_domain>.*?)', OPT_SPACE, r'\[(?P<from_ip>.*?)\]', r'\)', SPACE,
    ')?',
    'by', SPACE, r'(?P<by>.*?)', OPT_SPACE, r'(\((?P<by_comment>.*?)\))?', SPACE,
    'with', SPACE, r'(?P<with>.*?)', SPACE,
    'id', SPACE, r'(?P<id>.*?)', OPT_SPACE,
    '(', 'for', SPACE, r'(?P<for>.*?)', OPT_SPACE, '(', r'\(', r'(?P<for_comment>.*?)', r'\)', ')?', ')?',
    OPT_SPACE, ';', OPT_SPACE,
    r'(?P<date>.*)',
])

REGEX = re.compile(REGEX_STR, re.M)


def parse_received(received):
    '''
    Parse the information in the Received field.
    Will follow the RFC822.
    '''
    match = re.match(REGEX, received)
    if match:
        relay = dict(match.groupdict())

        # Date formatting
        date = relay.pop('date')
        try:
            relay['timestamp'] = parse(date).isoformat()
        except Exception:
            relay['timestamp'] = date

        relay = {k: v for k, v in relay.items() if v is not None}
        return relay
    else:
        return None
