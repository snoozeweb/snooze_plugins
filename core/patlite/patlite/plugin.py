'''Action plugin to send alerts to a Patlite'''

from patlite.utils.patlite import Patlite as PatliteAPI, State
from snooze.plugins.core import Plugin
from logging import getLogger, DEBUG
log = getLogger('snooze.action.patlite')
log.setLevel(DEBUG)

class Patlite(Plugin):
    def pprint(self, options):
        '''
        Determine the pretty print for the Patlite action plugin.
        This is how the information will be printed on the web interface
        to represent this action.
        '''
        host = options.get('host')
        port = options.get('port')
        output = host + ':' + str(port)
        sound = options.get('sound')
        state = [k+': '+v for k, v in options.get('lights', {}).items() if v != 'off']
        if sound:
            state.append("sound: " + sound)
        if state:
            output += ' @ ' + ' - '.join(state)
        return output

    def send(self, records, options):
        '''
        Determine the action that will be taken when this action is invoked.
        It will set the lights and alarm of the Patlite.
        '''
        lights = options.get('lights')
        sound = options.get('sound')
        state = lights.copy()
        if sound:
            state['sound'] = sound
        host = options.get('host')
        port = int(options.get('port'))
        log.debug("Will execute action patlite `%s:%s` state=%s", host, port, state)
        succeeded = records
        failed = []
        try:
            with PatliteAPI(host, port=port) as patlite:
                patlite.set_full_state(State(**state))
        except Exception as err:
            log.exception(err)
            succeeded = []
            failed = records
        return succeeded, failed
