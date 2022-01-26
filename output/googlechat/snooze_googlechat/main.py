import json
import falcon
import threading
import yaml
import os
import re
import sys
import logging
import socket
socket.setdefaulttimeout(10)
from datetime import datetime, timedelta
from dateutil import parser
from google.cloud import pubsub_v1
from apiclient.discovery import build
from concurrent.futures import TimeoutError
from google.oauth2 import service_account
from waitress.adjustments import Adjustments
from waitress.server import TcpWSGIServer
from socketserver import ThreadingMixIn
from pathlib import Path
from snooze_client import Snooze
from .bot_parser import parser as bot_parser

LOG = logging.getLogger("snooze.googlechat")

class Manager():

    date_regex = re.compile(r"[0-9]{1,4}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}[\+\d]*")
    duration_regex = re.compile(r"((\d+) *(mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y)|forever){0,1} *(.*)", re.IGNORECASE)

    def __init__(self, credentials, snooze_url=None, date_format=None, bot_name="Bot"):
        self.credendials = credentials
        self.chat = build('chat', 'v1', credentials=credentials)
        self.client = Snooze()
        self.bot_name = bot_name
        if snooze_url:
            if snooze_url.endswith('/'):
                self.snooze_url = snooze_url[:-1]
            else:
                self.snooze_url = snooze_url
        else:
            self.snooze_url = None
        if date_format:
            self.date_format = date_format
        else:
            self.date_format = '%a, %b %d, %Y at %I:%M %p'

    def send_message(self, message, space=None, thread=None):
        msg = {}
        msg['text'] = message
        if thread:
            space = '/'.join(thread.split('/')[:2])
            msg['thread'] = {}
            msg['thread']['name'] = thread
        LOG.debug('Posting on {} msg {}'.format(space, msg))
        for n in range(3):
            try:
                resp = self.chat.spaces().messages().create(parent=space, body=msg).execute()
                return resp
            except Exception as e:
                LOG.exception(e)
                continue
        return None

    def process_record(self, req):
        spaces = req.media['spaces']
        record = req.media['alert']
        message = req.media.get('message')
        reply = req.media.get('reply')
        action_name = req.params['snooze_action_name']

        LOG.debug('Received record: {}'.format(record))
        threads = next((action_result.get('content', {}).get('threads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), None)
        if threads:
            LOG.debug('Found threads: {}'.format(threads))
            if reply:
                msg = Manager.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), reply)
            elif message:
                msg = "*New escalation*\n" + message
            else:
                timestamp = Manager.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', datetime.now().astimezone()))
                msg = "*New escalation*\n*Date:* {}".format(timestamp)
            for thread in threads:
                self.send_message(msg, thread=thread)
        else:
            threads = []
            if message:
                msg = Manager.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message)
            else:
                if self.snooze_url:
                    website = self.snooze_url
                elif hasattr(req, 'forwarded_prefix') and req.forwarded_prefix:
                    website = req.forwarded_prefix
                else:
                    website = req.prefix
                timestamp = Manager.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', datetime.now().astimezone()))
                msg = "*Date:* {timestamp}\n*Host:* {host}\n*Source:* {source}\n*Process:* {process}\n*Severity:* {severity}\n*URL:* <{website}/web/?#/record?tab=All&s=hash%3D{rhash}|Snooze>\n*Message:* {message}".format(timestamp=timestamp, host=record.get('host', 'Unknown'), source=record.get('source', 'Unknown'), process=record.get('process', 'Unknown'), severity=record.get('severity', 'Unknown'), website=website, rhash=record.get('hash'), message=record.get('message', 'No message'))
            for space in spaces:
                resp = self.send_message(msg, space=space)
                threads.append(resp['thread']['name'])
        return threads

    def process_user_message(self, message):
        LOG.debug("Received message: '{}'".format(message))
        if 'argumentText' in message['message']:
            original_message = message['message']['argumentText'].lstrip()
            command, *text = message['message']['argumentText'].lstrip().split(' ')
        else:
            original_message = message['message']['text'].lstrip()
            command, *text = message['message']['text'].lstrip().split(' ')
        command = command.casefold()
        text = ' '.join(text)
        link = ''
        modification = []
        snooze_help = """Command: *@{}* snooze <duration> [condition]

*duration* (forever or X mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y): _Duration of this snooze entry_
*condition* (text): _Condition for which this snooze entry will match_

Example: _@{}_ *snooze* 6h host = example_host""".format(self.bot_name, self.bot_name)
        if command in ['help_snooze', '/help_snooze']:
            return snooze_help
        elif command in ['help', '/help']:
            if text == 'snooze':
                return snooze_help
            else:
                return """List of available commands:

*ack, acknowledge, ok* [message]: _Acknowledge an alert_
*esc, escalate, re-escalate, reescalate, re-esc, reesc* <modification> [message]: _Re-escalate an alert_
*close, done* [message]: _Close an alert_
*open, reopen, re-open* [message]: _Re-open an alert_
*snooze* <duration> [condition]: _Snooze an alert (default 1h) (_`/help_snooze`_)_
any other message: _Comment an alert_

Example: _@{}_ *esc* severity = critical _Please check_""".format(self.bot_name)
        thread = message['message']['thread']['name']
        aggregates = self.client.record(['IN', ['IN', thread, 'content.threads'], 'snooze_webhook_responses'])
        if len(aggregates) == 0:
            return 'Cannot find the corresponding alert!'
        record = aggregates[0]
        action_name = next(action_result.get('action_name') for action_result in record.get('snooze_webhook_responses', []) if thread in action_result.get('content', {}).get('threads', [])) or 'GoogleChatBot'
        user = '{} via {}'.format(message['user']['displayName'], action_name)
        if self.snooze_url:
            link = ' <{}/web/?#/record?tab=All&s=hash%3D{}|[Link]>'.format(self.snooze_url, record['hash'])
            snoozelink = ' <{}/web/?#/snooze?tab=All&s={}|[Link]>'.format(self.snooze_url, record['hash'])
        if command == 'snooze':
            LOG.debug("Snooze Record {} with parameters: '{}'".format(str(record), text))
            duration_match = Manager.duration_regex.search(text)
            if duration_match:
                try:
                    now = datetime.now()
                    time_constraint = {}
                    condition = []
                    query = ''
                    duration_time = duration_match.group(1)
                    duration_number = duration_match.group(2)
                    duration_period = duration_match.group(3)
                    query_match = duration_match.group(4)
                    if duration_time and duration_time == 'forever':
                        later = None
                        duration = 'Forever'
                    elif duration_period:
                        duration_period = duration_period.casefold()
                        if duration_period.startswith('h'):
                            later = now + timedelta(hours = int(duration_number))
                            duration = duration_number + ' hour(s)'
                        elif duration_period.startswith('d'):
                            later = now + timedelta(days = int(duration_number))
                            duration = duration_number + ' day(s)'
                        elif duration_period.startswith('w'):
                            later = now + timedelta(weeks = int(duration_number))
                            duration = duration_number + ' week(s)'
                        elif duration_period.startswith('month'):
                            later = now + timedelta(days = int(duration_number)*30)
                            duration = duration_number + ' month(s)'
                        elif duration_period.startswith('m'):
                            later = now + timedelta(minutes = int(duration_number))
                            duration = duration_number + ' minute(s)'
                        elif duration_period.startswith('y'):
                            later = now + timedelta(days = int(duration_number)*365)
                            duration = duration_number + ' year(s)'
                        else:
                            return "Invalid snooze filter duration syntax. Use `/help_snooze` to learn how to use this command"
                    else:
                        later = now + timedelta(hours = 1)
                        duration = '1h'
                    if query_match:
                        query = query_match
                    else:
                        condition = ['=', 'hash', '{}'.format(record['hash'])]
                    if later:
                        time_constraint = {"datetime": [{"from": now.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"), "until": later.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")}]}
                    result = self.client.snooze('[{}] {}'.format(duration, record['hash']), condition=condition, ql=query, time_constraint=time_constraint)
                    if result.get('rejected'):
                        return "Could not snooze alert! (Possibly a duplicate filter)"
                    LOG.debug('Done: {}'.format(result))
                    if later:
                        return 'Snoozed for {}! Expires at *{}*{}'.format(duration, later.strftime(self.date_format), snoozelink)
                    else:
                        return 'Snoozed forever! {}'.format(snoozelink)
                except Exception as e:
                    LOG.debug(e)
                    return 'Could not snooze alert!'
            else:
                return "Invalid snooze filter syntax. Use `/help_snooze` to learn how to use this command"
        elif command in ['ack', 'acknowledge', 'ok']:
            LOG.debug('ACK Record {}'.format(str(record)))
            try:
                self.client.comment('ack', user, 'google', record['uid'], text)
                return 'Alert acknowledged successfully!' + link
            except Exception as e:
                LOG.debug(e)
                return 'Could not acknowledge alert!'
        elif command in ['esc', 'escalate', 're-escalate', 'reescalate', 're-esc', 'reesc']:
            LOG.debug('ESC Record {}'.format(str(record)))
            try:
                modifications, comment = bot_parser(text)
                self.client.comment('esc', user, 'google', record['uid'], comment, modifications)
                return 'Alert re-escalated successfully!' + link
            except Exception as e:
                LOG.debug(e)
                return 'Could not re-escalate alert!'
        elif command in ['close', 'done']:
            LOG.debug('CLOSE Record {}'.format(str(record)))
            try:
                self.client.comment('close', user, 'google', record['uid'], text)
                return 'Alert closed successfully!' + link
            except Exception as e:
                LOG.debug(e)
                return 'Could not close alert!'
        elif command in ['open', 'reopen', 're-open']:
            LOG.debug('OPEN Record {}'.format(str(record)))
            try:
                self.client.comment('open', user, 'google', record['uid'], text)
                return 'Alert re-opened successfully!' + link
            except Exception as e:
                LOG.debug(e)
                return 'Could not re-open alert!'
        else:
            LOG.debug('COMMENT Record {}'.format(str(record)))
            try:
                self.client.comment('', user, 'google', record['uid'], original_message)
                return 'Comment added successfully! ' + link
            except Exception as e:
                LOG.exception(e)
                return 'Could not comment the alert!'

class AlertRoute():

    def __init__(self, manager):
        self.manager = manager

    def on_post(self, req, resp):
        threads = self.manager.process_record(req)
        LOG.debug("Threads: {}".format(threads))
        resp.status = falcon.HTTP_200
        if threads:
            resp.content_type = falcon.MEDIA_JSON
            resp.media = {
                'threads': threads,
            }

class PubSub(threading.Thread):

    def __init__(self, manager, credentials, subscription_name):
        super(PubSub, self).__init__()
        self.manager = manager
        self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        subscription_path = self.subscriber.subscription_path(credentials.project_id, subscription_name)
        self.future = self.subscriber.subscribe(subscription_path, self.callback)

    def callback(self, message):
        data = json.loads(message.data)
        if data['type'] == 'MESSAGE':
            return_msg = self.manager.process_user_message(data)
            self.manager.send_message(return_msg, thread=data['message']['thread']['name'])
        message.ack()

    def wait_for_messages(self):
        LOG.debug("Wait for messages...")
        with self.subscriber:
            try:
                self.future.result()
            except TimeoutError:
                self.future.cancel()
                self.future.result()

    def run(self):
        self.wait_for_messages()

    def kill(self):
        self.future.cancel()
        self.future.result()
        self.join()


class GoogleChatBot():

    def __init__(self):
        scope = 'https://www.googleapis.com/auth/chat.bot'
        self.load_config()
        level = logging.INFO
        if self.config.get('debug', False):
            level = logging.DEBUG
        logging.basicConfig(format="%(asctime)s - %(name)s: %(levelname)s - %(message)s", level=level)
        if 'subscription_name' not in self.config:
            LOG.error("Missing parameter 'subscription_name' in /etc/snooze/googlechat.yaml")
            sys.exit()
        credentials = service_account.Credentials.from_service_account_file(self.config.get('service_account_path',  os.environ['HOME'] + '/.sa_secrets.json'))
        scoped_credentials = credentials.with_scopes([scope])

        self.address = self.config.get('listening_address', '0.0.0.0')
        self.port = self.config.get('listening_port', 5201)
        self.app = falcon.App()
        self.manager = Manager(scoped_credentials, self.config.get('snooze_url'), self.config.get('date_format'), self.config.get('bot_name', 'Bot'))
        self.pubsub = PubSub(self.manager, credentials, self.config.get('subscription_name'))
        self.pubsub.start()
        self.app.add_route('/alert', AlertRoute(self.manager))

    def load_config(self):
        config_file = os.environ.get('SNOOZE_GOOGLE_CHATBOT_CONFIG_FILE', '/etc/snooze/googlechat.yaml')
        path = Path(config_file)
        if path.exists():
            self.config = yaml.safe_load(path.read_text())
        else:
            self.config = {}

    def serve(self):
        wsgi_options = Adjustments(host=self.address, port=self.port)
        httpd = TcpWSGIServer(self.app, adj=wsgi_options)
        LOG.info("Serving on port {}...".format(str(self.port)))
        httpd.run()
        LOG.info("Exiting PubSub...")
        self.pubsub.kill()
        LOG.info("Shutting down...")


def main():
    GoogleChatBot().serve()

if __name__ == '__main__':
    main()
