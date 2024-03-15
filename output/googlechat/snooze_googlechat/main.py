import json
import falcon
import threading
import yaml
import os
import re
import sys
import logging
import socket
import uuid
import time
import httplib2
import google_auth_httplib2
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
from .bot_emoji import parse_emoji

LOG = logging.getLogger("snooze.googlechat")
logging.getLogger('google').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.WARNING)

class GoogleChatBot():

    date_regex = re.compile(r"[0-9]{1,4}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}[\+\d]*")
    duration_regex = re.compile(r"((\d+) *(mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y)|forever){0,1} *(.*)", re.IGNORECASE)

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
        self.credentials = credentials.with_scopes([scope])
        self.address = self.config.get('listening_address', '0.0.0.0')
        self.port = self.config.get('listening_port', 5201)
        self.app = falcon.App()
        self.date_format = self.config.get('date_format', '%a, %b %d, %Y at %I:%M %p')
        self.client = Snooze()
        self.bot_name = self.config.get('bot_name', 'Bot')
        self.snooze_url = self.config.get('snooze_url', '')
        self.message_limit = self.config.get('message_limit', 10)
        self.snooze_limit = self.config.get('snooze_limit', self.message_limit)
        self.use_card = self.config.get('use_card', False)
        if self.snooze_url.endswith('/'):
            self.snooze_url = self.snooze_url[:-1]
        self.pubsub = PubSub(self, credentials)
        self.pubsub.start()
        self.app.add_route('/alert', AlertRoute(self))

    def load_config(self):
        config_path = Path(os.environ.get('SNOOZE_GOOGLE_CHATBOT_PATH', '/etc/snooze'))
        config_file = config_path / 'googlechat.yaml'
        if config_file.exists():
            self.config = yaml.safe_load(config_file.read_text())
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

    def send_message(self, message, space=None, thread=None, attachment=None):
        msg = {}
        msg['text'] = message
        if thread:
            space = '/'.join(thread.split('/')[:2])
            msg['thread'] = {}
            msg['thread']['name'] = thread
            reply_option = 'REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD'
        else:
            reply_option = 'MESSAGE_REPLY_OPTION_UNSPECIFIED'
        LOG.debug('Posting on {} msg {}'.format(space, msg))
        chat = build('chat', 'v1', credentials=self.credentials)
        if attachment:
            msg['cards'] = [{'sections': [{'widgets': [{'buttons': [{'textButton': {'text': button.get('text'), 'onClick': {'action': {'actionMethodName': button.get('action')}}}} for button in attachment]}]}]}]
        for n in range(3):
            try:
                resp = chat.spaces().messages().create(parent=space, messageReplyOption=reply_option, body=msg).execute()
                LOG.debug("Received response: %s", str(resp))
                return resp
            except Exception as e:
                LOG.exception(e)
                time.sleep(1)
                continue
        return None

    def process_records(self, req, medias):
        multi = len(medias) > 1
        spaces = {}
        header = ''
        footer = ''
        website = ''
        return_value = {}
        attachment = {}
        if self.snooze_url:
            website = self.snooze_url
        elif hasattr(req, 'forwarded_prefix') and req.forwarded_prefix:
            website = req.forwarded_prefix
        else:
            website = req.prefix
        action_name = req.params['snooze_action_name']
        for req_media in medias[:self.message_limit]:
            self.process_rec(spaces, req_media, action_name, multi, website)
        for req_media in medias[self.message_limit:]:
            self.process_rec(spaces, req_media, action_name, multi, website, False)
        for space, content in spaces.items():
            if multi:
                timestamp = datetime.now().astimezone().strftime(self.date_format)
                header = parse_emoji('::warning:: Received *{}* alerts on {} ::warning::\n\n'.format(len(content), timestamp))
                if len(content) > self.message_limit:
                    footer = '\n...\n\nCheck all alerts in <{}/web|SnoozeWeb>'.format(website)
            if self.use_card:
                attachment = [{'text': 'Acknowledge', 'action': 'ack', 'style': 'success'}, {'text': 'Help', 'action': 'help', 'style': 'primary'}]
            if not multi and content[0]['threads']:
                for thread in content[0]['threads']:
                    self.send_message(content[0]['msg'], thread=thread, attachment=attachment)
                return_value = {content[0]['record_hash']: {'threads': content[0]['threads'], 'multithreads': content[0]['multithreads']}}
            else:
                resp = self.send_message(header + '\n'.join([message['msg'] for message in content if len(message['msg']) > 0]) + footer, space=space, attachment=attachment)
                for message in content:
                    if multi:
                        message['multithreads'].append(resp['thread']['name'])
                    else:
                        message['threads'].append(resp['thread']['name'])
                    return_value[message['record_hash']] = {'threads': message['threads'], 'multithreads': message['multithreads']}
        if multi:
            return return_value
        else:
            return list(return_value.values())[0]

    def process_rec(self, spaces, req_media, action_name, multi, website, process = True):
        rec_spaces = req_media['spaces']
        record = req_media['alert']
        message = req_media.get('message')
        message_group = req_media.get('message_group')
        reply = req_media.get('reply')
        notification_from = record.get('notification_from')

        LOG.debug('Received record: {}'.format(record))
        msg = ''
        threads = next((action_result.get('content', {}).get('threads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        multithreads = next((action_result.get('content', {}).get('multithreads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        if process:
            if multi:
                msg = parse_emoji('::black-square-small::')
            if notification_from:
                notif_name = notification_from.get('name', 'anonymous')
                notif_message = notification_from.get('message')
                if multi:
                    msg += '`{}` '.format(notif_name)
                else:
                    msg += 'From `{}`'.format(notif_name)
                    if notif_message:
                        msg += ': {}'.format(notif_message)
                    msg += "\n\n"
            if threads and not multi:
                LOG.debug('Found threads: {}'.format(threads))
                if reply:
                    msg += GoogleChatBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), reply)
                elif message:
                    msg += parse_emoji("::warning:: *New escalation* ::warning::\n") + message
                else:
                    timestamp = GoogleChatBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', str(datetime.now().astimezone())))
                    msg += parse_emoji("::warning:: *New escalation* ::warning::\n*Date:* {}".format(timestamp))
            else:
                if multi:
                    if threads:
                        msg += '*[Esc]* '
                    if message_group:
                        msg += GoogleChatBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message_group)
                    else:
                        msg += "[{source}] <{website}/web/?#/record?tab=All&s=hash%3D{rhash}|{host}> `{process}` {message}".format(source=record.get('source', 'Unknown'), website=website, rhash=record.get('hash'), host=record.get('host', 'Unknown'), process=record.get('process', 'Unknown'), message=record.get('message', 'No message'))
                else:
                    if message:
                        msg += GoogleChatBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message)
                    else:
                        timestamp = GoogleChatBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', datetime.now().astimezone()))
                        msg += "*Date:* {timestamp}\n*Host:* {host}\n*Source:* {source}\n*Process:* {process}\n*Severity:* {severity}\n*URL:* <{website}/web/?#/record?tab=All&s=hash%3D{rhash}|Snooze>\n*Message:* {message}".format(timestamp=timestamp, host=record.get('host', 'Unknown'), source=record.get('source', 'Unknown'), process=record.get('process', 'Unknown'), severity=record.get('severity', 'Unknown'), website=website, rhash=record.get('hash'), message=record.get('message', 'No message'))
        for space in rec_spaces:
            if space not in spaces:
                spaces[space] = []
            spaces[space].append({'msg': msg, 'record_hash': record.get('hash', ''), 'threads': threads, 'multithreads': multithreads})

    def process_user_message(self, message):
        LOG.debug("Received message: '{}'".format(message))
        if 'slashCommand' in message['message']:
            original_message = message['message']['text'].lstrip()
        elif 'argumentText' in message['message']:
            original_message = message['message']['argumentText'].lstrip()
        else:
            original_message = message['message']['text'].lstrip()
        try:
            command, text = re.split(r'[^a-zA-Z0-9\/]', original_message, 1)
        except ValueError:
            command = original_message
            text = ''
        command = command.casefold()
        link = ''
        snoozelink = ''
        modification = []
        display_name = message['user']['displayName']
        snooze_help = """`{}`: Command: *@{}* snooze <duration> [condition]

*duration* (forever or X mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y): _Duration of this snooze entry_
*condition* (text): _Condition for which this snooze entry will match_

Example: _@{}_ *snooze* 6h host = example_host""".format(display_name, self.bot_name, self.bot_name)
        if command in ['help_snooze', '/help_snooze']:
            return snooze_help
        elif not command or command in ['help', '/help']:
            if text == 'snooze':
                return snooze_help
            else:
                return """`{}`: List of available commands:

*ack, acknowledge, ok* [message]: _Acknowledge an alert_
*esc, escalate, re-escalate, reescalate, re-esc, reesc* <modification> [message]: _Re-escalate an alert_
*close, done* [message]: _Close an alert_
*open, reopen, re-open* [message]: _Re-open an alert_
*snooze* <duration> [condition]: _Snooze an alert (default 1h) (_`/help_snooze`_)_
any other message: _Comment an alert_

Example: _@{}_ *esc* severity = critical _Please check_""".format(display_name, self.bot_name)
        thread = message['message']['thread']['name']
        aggregates = self.client.record(['OR', ['IN', ['IN', thread, 'content.threads'], 'snooze_webhook_responses'], ['IN', ['IN', thread, 'content.multithreads'], 'snooze_webhook_responses']])
        if len(aggregates) == 0:
            return parse_emoji('::cross-mark:: `{}`:Cannot find the corresponding alert! (command: `{}`)'.format(display_name, original_message))
        record = aggregates[0]
        action_name = next(action_result.get('action_name') for action_result in record.get('snooze_webhook_responses', []) if thread in action_result.get('content', {}).get('threads', []) + action_result.get('content', {}).get('multithreads', [])) or 'GoogleChatBot'
        user = '{} via {}'.format(display_name, action_name)
        if self.snooze_url:
            link = '<{}/web/?#/record?tab=All&s=hash%3D{}|[Link]>'.format(self.snooze_url, record['hash'])
            snoozelink = '<{}/web/?#/snooze?tab=All&s=hash%3D{}|[Link]>'.format(self.snooze_url, record['hash'])
        if command in ['snooze', '/snooze']:
            LOG.debug("Snooze {} alerts with parameters: '{}'".format(len(aggregates), text))
            duration_match = GoogleChatBot.duration_regex.search(text)
            if duration_match:
                try:
                    now = datetime.now()
                    time_constraints = {}
                    conditions = []
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
                            return parse_emoji("::cross-mark:: `{}`: Invalid snooze filter duration syntax. Use `/help_snooze` to learn how to use this command".format(display_name))
                    else:
                        later = now + timedelta(hours = 1)
                        duration = '1h'
                    if query_match:
                        query = query_match
                        conditions = [None]
                    else:
                        conditions = []
                        for record in aggregates:
                            conditions.append(['=', 'hash', '{}'.format(record['hash'])])
                    if later:
                        time_constraints = {"datetime": [{"from": now.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"), "until": later.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")}]}
                    if len(conditions) <= self.snooze_limit:
                        payload = [{'name': '[{}] {} ({})'.format(duration, display_name, str(uuid.uuid4())[:5]), 'condition': condition, 'ql': query, 'time_constraints': time_constraints, 'comment': display_name} for condition in conditions]
                        result = self.client.snooze_batch(payload)
                        if result.get('rejected'):
                            return parse_emoji('::cross-mark:: `{}`: Could not Snooze alert(s)!'.format(display_name))
                        LOG.debug('Done: {}'.format(result))
                        ack_payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': 'Snoozed for {}'.format(duration)} for record in aggregates]
                        self.client.comment_batch(ack_payload)
                        count = ''
                        if len(aggregates) > 1:
                            link = '<{}/web/?#/record?tab=Acknowledged|[Link]>'.format(self.snooze_url)
                            snoozelink = '<{}/web/?#/snooze?tab=All|[Link]>'.format(self.snooze_url)
                            count = '*{}* '.format(len(aggregates))
                        comment_text = parse_emoji("::check-mark:: {}Alert(s) acknowledged successfully by `{}`! {}\n".format(count, display_name, link))
                        warning_text = ''
                        if len(result['data'].get('added', [])) > 0:
                            res_cond = result['data']['added'][0].get('condition', [])
                            if len(res_cond) > 0 and res_cond[0] == 'SEARCH':
                                warning_text = parse_emoji("\n::warning:: Snooze filter condition `{}` might not be expected. Please double check in the Web interface".format(res_cond))
                        if later:
                            return comment_text + parse_emoji('::check-mark::') + ' Snoozed for {}! Expires at *{}* {}'.format(duration, later.strftime(self.date_format), snoozelink) + warning_text
                        else:
                            return comment_text + parse_emoji('::check-mark::') + ' Snoozed forever! {}'.format(snoozelink) + warning_text
                    else:
                        return parse_emoji('::cross-mark:: `{}`: Cannot Snooze more than {} alert(s) without using an explicit condition. Please try again or use <{}/web/?#/snooze|SnoozeWeb>.'.format(display_name, self.snooze_limit, self.snooze_url))
                except Exception as e:
                    LOG.exception(e)
                    return parse_emoji('::cross-mark:: `{}`: Could not Snooze alert(s)!'.format(display_name))
            else:
                return "`{}`: Invalid Snooze filter syntax. Use `/help_snooze` to learn how to use this command".format(display_name)
        elif command in ['ack', 'acknowledge', 'ok', '/ack']:
            LOG.debug('ACK {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return parse_emoji('::check-mark:: Alert acknowledged successfully by `{}`{}! {}'.format(display_name, msg_extra, link))
                else:
                    return parse_emoji('::check-mark:: *{}* alerts acknowledged successfully by `{}`{}! <{}/web/?#/record?tab=Acknowledged|[Link]>'.format(len(aggregates), display_name, msg_extra, self.snooze_url))
            except Exception as e:
                LOG.exception(e)
                return parse_emoji('::cross-mark:: `{}`: Could not acknowledge alert(s)!'.format(display_name))
        elif command in ['esc', 'escalate', 're-escalate', 'reescalate', 're-esc', 'reesc', '/esc']:
            LOG.debug('ESC {} alerts'.format(len(aggregates)))
            try:
                modifications, comment = bot_parser(text)
                payload = [{'type': 'esc', 'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': comment, 'modifications': modifications} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if modifications:
                    msg_extra += ' with modification `{}`'.format(modifications)
                if comment:
                    msg_extra += ' {} message `{}`'.format('and' if modifications else 'with', comment)
                if len(aggregates) == 1:
                    return parse_emoji('::check-mark:: Alert re-escalated successfully by `{}`{}! {}'.format(display_name, msg_extra, link))
                else:
                    return parse_emoji('::check-mark:: *{}* alerts re-escalated successfully by `{}`{}! <{}/web/?#/record?tab=Re-escalated|[Link]>'.format(len(aggregates), display_name, msg_extra, self.snooze_url))
            except Exception as e:
                LOG.exception(e)
                return parse_emoji('::cross-mark:: `{}`: Could not re-escalate alert(s)!'.format(display_name))
        elif command in ['close', 'done', '/close']:
            LOG.debug('CLOSE {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'close', 'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return parse_emoji('::check-mark:: Alert closed successfully by `{}`{}! {}'.format(display_name, msg_extra, link))
                else:
                    return parse_emoji('::check-mark:: *{}* alerts closed successfully by `{}`{}! <{}/web/?#/record?tab=Closed|[Link]>'.format(len(aggregates), display_name, msg_extra, self.snooze_url))
            except Exception as e:
                LOG.exception(e)
                return parse_emoji('::cross-mark:: `{}`: Could not close alert(s)!'.format(display_name))
        elif command in ['open', 'reopen', 're-open', '/open']:
            LOG.debug('OPEN {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'open', 'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return parse_emoji('::check-mark:: Alert re-opened successfully by `{}`{}! {}'.format(display_name, msg_extra, link))
                else:
                    return parse_emoji('::check-mark:: *{}* alerts re-opened successfully by `{}`{}! <{}/web/?#/record?tab=Alerts&s=state=open|[SnoozeWeb]>'.format(len(aggregates), display_name, msg_extra, self.snooze_url))
            except Exception as e:
                LOG.exception(e)
                return parse_emoji('::cross-mark:: `{}`: Could not re-open alert(s)!'.format(display_name))
        else:
            LOG.debug('COMMENT {} alerts'.format(len(aggregates)))
            try:
                msg_extra = ''
                if command in ['/comment']:
                    msg_extra = text
                else:
                    msg_extra = original_message
                payload = [{'record_uid': record['uid'], 'name': user, 'method': 'google', 'message': msg_extra} for record in aggregates]
                self.client.comment_batch(payload)
                if len(aggregates) == 1:
                    return parse_emoji('::check-mark:: Comment added successfully by `{}`: `{}`! {}'.format(display_name, msg_extra, link))
                else:
                    return parse_emoji('::check-mark:: *{}* comments added successfully by `{}`: `{}`! <{}/web/?#/record|[Link]>'.format(len(aggregates), display_name, msg_extra, self.snooze_url))
            except Exception as e:
                LOG.exception(e)
                return parse_emoji('::cross-mark:: `{}`: Could not comment alert(s)!'.format(display_name))

class AlertRoute():

    def __init__(self, manager):
        self.manager = manager

    def on_post(self, req, resp):
        medias = req.media
        if not isinstance(medias, list):
            medias = [medias]
        response = self.manager.process_records(req, medias)
        LOG.debug("Response: {}".format(response))
        resp.status = falcon.HTTP_200
        if response:
            resp.content_type = falcon.MEDIA_JSON
            resp.media = response

class PubSub(threading.Thread):

    def __init__(self, manager, credentials):
        super(PubSub, self).__init__()
        self.manager = manager
        self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        subscription_path = self.subscriber.subscription_path(credentials.project_id, self.manager.config.get('subscription_name'))
        self.future = self.subscriber.subscribe(subscription_path, self.callback)

    def callback(self, message):
        data = json.loads(message.data)
        if data['type'] == 'MESSAGE':
            return_msg = self.manager.process_user_message(data)
            self.manager.send_message(return_msg, thread=data['message']['thread']['name'])
        elif data['type'] == 'CARD_CLICKED':
            data['message']['text'] = data['action']['actionMethodName']
            data['message'].pop('argumentText', '')
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


def main():
    GoogleChatBot().serve()

if __name__ == '__main__':
    main()
