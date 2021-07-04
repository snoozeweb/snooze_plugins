'''RELP input plugin for snooze server'''

import logging
import os
import platform
import re
import ssl
import sys
import yaml

from pathlib import Path

from snooze_client import Snooze
from relp.server import RelpServer

SYSLOG_FACILITY_NAMES = [
    "kern",
    "user",
    "mail",
    "daemon",
    "auth",
    "syslog",
    "lpr",
    "news",
    "uucp",
    "cron",
    "authpriv",
    "ftp",
    "ntp",
    "audit",
    "alert",
    "clock",
    "local0",
    "local1",
    "local2",
    "local3",
    "local4",
    "local5",
    "local6",
    "local7"
]

SYSLOG_SEVERITY_NAMES = [
    "emerg",
    "alert",
    "crit",
    "err",
    "warning",
    "notice",
    "info",
    "debug"
]

def decode_priority(pri):
    '''Decode the syslog facility and severity from the PRI'''
    facility = pri >> 3
    severity = pri & 7
    return SYSLOG_FACILITY_NAMES[facility], SYSLOG_SEVERITY_NAMES[severity]

LOG = logging.getLogger("snooze.relp")
logging.basicConfig(format="%(asctime)s - %(name)s: %(levelname)s - %(message)s", level=logging.DEBUG)

def parse_rfc3164(msg):
    '''Parse Syslog RFC 3164 message format'''
    m = re.match(r'<(\d{1,3})>\S{3}\s{1,2}\d?\d \d{2}:\d{2}:\d{2} (\S+)( (\S+):)? (.*)', msg)
    if m:
        record = {
            'syslog_type': 'rfc3164',
            'pri': int(m.group(1)),
            'host': m.group(2),
            'message': m.group(5),
        }

        process = m.group(4)
        if process:
            record['process'] = process

        return record
    else:
        raise Exception("Could not parse RFC 3164 syslog message: %s" % msg)

def parse_rfc5424(msg):
    '''Parse Syslog RFC 5424 message format'''
    m = re.match(r'<(\d+)>1 (\S+) (\S+) (\S+) (\S+) (\S+) (.*)', msg)
    if m:
        record = {
            'syslog_type': 'rfc5424',
            'pri': int(m.group(1)),
            'timestamp': m.group(2),
            'host': m.group(3),
            'process': m.group(4),
            'pid': m.group(5),
            'msgid': m.group(6),
            'message': m.group(7),
        }
        return record
    else:
        raise Exception("Could not parse RFC 5424 syslog message: %s" % msg)

def parse_cisco(msg):
    '''Parse Cisco Syslog message format'''
    m = re.match('<(\d+)>.*(%([A-Z0-9_-]+)):? (.*)', msg)
    if m:
        record = {
            'syslog_type': 'cisco',
            'pri': int(m.group(1)),
            'message': m.group(4)
        }
        try:
            facility, severity, mnemonic = m.group(3).split('-')
        except ValueError as err:
            LOG.error('Could not parse Cisco syslog - %s: %s', err, m.group(3))
            facility = severity = mnemonic = 'na'
        record.update({
            'cisco_facility': facility,
            'cisco_severity': severity,
            'cisco_mnemonic': mnemonic,
        })

        return record
    else:
        raise Exception("Could not parse Cisco syslog message: %s" % msg)

def parse_syslog(ipaddr, data):
    '''Parse a syslog message from the queue'''
    LOG.debug('Parsing syslog message...')
    records = list()

    for msg in data.strip().split('\n'):
        LOG.debug("Found: %s", msg)
        record = dict()

        record['source_ip'] = ipaddr

        if not msg or 'last message repeated' in msg:
            LOG.debug("Skipping message: %s", msg)
            continue

        if re.match(r'<\d+>1', msg):
            record.update(parse_rfc5424(msg))

        elif re.match(r'<(\d{1,3})>\S{3}\s', msg):
            record.update(parse_rfc3164(msg))

        elif re.match(r'<\d+>.*%[A-Z0-9_-]+', msg):
            record.update(parse_cisco(msg))

        else:
            LOG.error("Could not parse message: %s", msg)
            continue

        record['source'] = 'relp'
        record['raw'] = msg

        facility, severity = decode_priority(record['pri'])
        record.update({
            'facility': facility,
            'severity': severity,
        })

        records.append(record)

    return records

class RelpDaemon(object):
    def __init__(self):
        self.load_config()

        # Config and defaults
        snooze_uri = self.config.get('snooze_server')
        self.api = Snooze(snooze_uri)

        self.listening_address = self.config.get('listening_address', '0.0.0.0')
        self.listening_port = self.config.get('listening_port', 2514)

        self.relp_server = RelpServer(self.listening_address, self.listening_port, self.handler, LOG)

    def load_config(self):
        self.config = {}
        config_file = os.environ.get('SNOOZE_RELP_CONFIG') or '/etc/snooze/relp.yaml'
        config_file = Path(config_file)
        try:
            with config_file.open('r') as myfile:
                self.config = yaml.safe_load(myfile.read())
        except Exception as err:
            LOG.error("Error loading config: %s", err)
        if not isinstance(self.config, dict):
            self.config = {}

    def serve_forever(self):
        self.relp_server.serve_forever()

    def handler(self, message):
        #client_addr = self.client_address[0].encode().decode()
        client_addr = ''
        LOG.debug(f"[relp] Received from {client_addr}: {message}")
        records = parse_syslog(client_addr, message)
        for record in records:
            LOG.debug(f"Sending record to snooze: {record}")
            self.api.alert(record)

def main():
    LOG = logging.getLogger("snooze.relp")
    try:
        LOG.info("Starting snooze relp daemon")
        daemon = RelpDaemon()
        daemon.serve_forever()
    except (SystemExit, KeyboardInterrupt):
        LOG.info("Exiting snooze relp daemon")
        sys.exit(0)
    except Exception as e:
        LOG.error(e, exc_info=1)
        sys.exit(1)

if __name__ == '__main__':
    main()
