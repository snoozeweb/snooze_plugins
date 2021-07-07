'''RELP input plugin for snooze server'''

import logging
import os
import sys
import yaml

from pathlib import Path

from snooze_client import Snooze
from snooze_syslog.parser import parse_syslog
from relp.server import RelpServer

LOG = logging.getLogger("snooze.relp")
logging.basicConfig(
    format="%(asctime)s - %(name)s: %(levelname)s - %(message)s",
    level=logging.DEBUG
)

class RelpDaemon(object):
    '''
    A class to represent the daemon listening for syslog message
    in RELP, and sending it to the Snooze server.
    '''
    def __init__(self):
        self.load_config()

        # Config and defaults
        snooze_uri = self.config.get('snooze_server')
        self.api = Snooze(snooze_uri)

        self.listening_address = self.config.get('listening_address', '0.0.0.0')
        self.listening_port = self.config.get('listening_port', 2514)

        self.relp_server = RelpServer(self.listening_address, self.listening_port, self.handler, LOG)

    def load_config(self):
        '''Load the configuration file'''
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
        '''Serve the daemon forever'''
        self.relp_server.serve_forever()

    def handler(self, message):
        '''The handler function that will be applied for every message received'''
        #client_addr = self.client_address[0].encode().decode()
        client_addr = ''
        LOG.debug("[relp] Received from %s: %s", client_addr, message)
        records = parse_syslog(client_addr, message, 'relp')
        for record in records:
            LOG.debug("Sending record to snooze: %s", record)
            self.api.alert(record)

def main():
    '''Main function to run the daemon'''
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
