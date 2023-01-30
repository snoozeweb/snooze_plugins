import json
import yaml
import os
import re
import logging
import uuid
import time
import falcon
from datetime import datetime, timedelta
from dateutil import parser
from pathlib import Path
from string import Template
from snooze_client import Snooze
from snooze_teams.bot_parser import parser as bot_parser
from snooze_teams.bot_emoji import parse_emoji

from waitress.adjustments import Adjustments
from waitress.server import TcpWSGIServer
from O365 import Account, MSGraphProtocol

LOG = logging.getLogger("snooze.teamschat")

class SnoozeBot():

    def __init__(self, env_name, file_name, plugin_class = "SnoozeBotPlugin"):
        self.reload_config(env_name, file_name)
        level = logging.INFO
        if self.config.get('debug', False):
            level = logging.DEBUG
        logformat = "%(asctime)s - %(name)s: %(levelname)s - %(message)s"
        logging.getLogger("").handlers.clear()
        logging.basicConfig(format=logformat, level=level)
        self.plugin = globals()[plugin_class](self.config)

    def reload_config(self, env_name, file_name):
        config_path = Path(os.environ.get(env_name, '/etc/snooze'))
        config_file = config_path / file_name
        if config_file.exists():
            self.config = yaml.safe_load(config_file.read_text())
        else:
            self.config = {}

class SnoozeBotPlugin():

    date_regex = re.compile(r"[0-9]{1,4}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}[\+\d]*")
    duration_regex = re.compile(r"((\d+) *(mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y)|forever){0,1} *(.*)", re.IGNORECASE)

    def __init__(self, config):
        self.config = config
        self.address = self.config.get('listening_address', '0.0.0.0')
        self.port = self.config.get('listening_port', 5202)
        self.date_format = self.config.get('date_format', '%a, %b %d, %Y at %I:%M %p')
        self.client = Snooze()
        self.bot_name = self.config.get('bot_name', 'Bot')
        self.snooze_url = self.config.get('snooze_url', 'http://localhost:5201')
        if self.snooze_url.endswith('/'):
            self.snooze_url = self.snooze_url[:-1]
        self.message_limit = self.config.get('message_limit', 10)
        self.snooze_limit = self.config.get('snooze_limit', self.message_limit)
    
    def process_alert(self, request, medias):
        if not isinstance(medias, list):
            medias = [medias]
        response = self.process_records(request, medias)
        LOG.debug("Response: {}".format(response))
        return response

    def send_message(self, message, channel_id="", thread={}, attachment={}, request={}):
        return

    def process_records(self, req, medias):
        multi = len(medias) > 1
        channels = {}
        header = False
        footer = False
        return_value = {}
        website = self.snooze_url
        action_name = req.params['snooze_action_name']
        for req_media in medias[:self.message_limit]:
            self.process_rec(channels, req_media, action_name, multi, website)
        for req_media in medias[self.message_limit:]:
            self.process_rec(channels, req_media, action_name, multi, website, False)
        for channel, content in channels.items():
            if multi:
                header = True
                if len(content) > self.message_limit:
                    footer = True
            attachment = [{'text': 'Acknowledge', 'action': 'ack', 'style': 'success'}, {'text': 'Close', 'action': 'close', 'style': 'primary'}]
            if not multi and content[0]['threads']:
                for thread in content[0]['threads']:
                    self.send_message(content[0]['msg'], channel_id=channel, thread=thread, attachment=attachment, request=req)
                return_value = {content[0]['record_hash']: {'threads': content[0]['threads'], 'multithreads': content[0]['multithreads']}}
            else:
                resp = self.send_message({'header': header, 'footer': footer, 'messages': content}, channel_id=channel, attachment=attachment, request=req)
                for message in content:
                    t = {'channel_id': channel, 'thread_id': resp.get('root_id', resp['id'])}
                    if multi:
                        message['multithreads'].append(t)
                    else:
                        message['threads'].append(t)
                    return_value[message['record_hash']] = {'threads': message['threads'], 'multithreads': message['multithreads']}
        if multi:
            return return_value
        else:
            return list(return_value.values())[0]

    def process_rec(self, channels,req_media, action_name, multi, website, process = True):
        rec_channels = req_media['channels']
        record = req_media['alert']
        message = req_media.get('message')
        message_group = req_media.get('message_group')
        reply = req_media.get('reply')
        notification_from = record.get('notification_from')

        LOG.debug('Received record: {}'.format(record))
        msg = {}
        threads = next((action_result.get('content', {}).get('threads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        multithreads = next((action_result.get('content', {}).get('multithreads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        if process:
            msg['record'] = record
            if multi:
                msg['multi'] = True
            if threads:
                msg['threads'] = True
            if reply:
                msg['reply'] = reply
            if message:
                msg['message'] = message
            if message_group:
                msg['message_group'] = message_group
            if notification_from:
                notif_name = notification_from.get('name', 'anonymous')
                notif_message = notification_from.get('message')
                msg['from'] = notif_name
                if notif_message:
                    msg['from_msg'] = notif_message
        for channel in rec_channels:
            if channel not in channels:
                channels[channel] = []
            channels[channel].append({'msg': msg, 'record_hash': record.get('hash', ''), 'threads': threads, 'multithreads': multithreads})

    def process_user_message(self, message):
        LOG.debug("Received message: '{}'".format(vars(message)))
        try:
            display_name = message.user_name
            thread = message.root_id
            if 'command' in message.body:
                original_message = message.command + ' ' + message.text.lstrip()
            else:
                original_message = message.text.lstrip()
        except:
            display_name = message.sender_name
            original_message = message.text.lstrip()
            thread = message.root_id or message.id
        try:
            command, text = re.split(r'[^a-zA-Z0-9\/]', original_message, 1)
        except ValueError:
            command = original_message
            text = ''
        command = command.casefold()
        link = ''
        snoozelink = ''
        modification = []
        snooze_help = """`{}`: Command: **@{}** snooze <duration> [condition]

**duration** (forever or X mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y): *Duration of this snooze entry*
**condition** (text): *Condition for which this snooze entry will match*

Example: *@{}* **snooze** 6h host = example_host""".format(display_name, self.bot_name, self.bot_name)
        if command in ['help_snooze', '/help_snooze']:
            return snooze_help
        elif not command or command in ['help', '/help']:
            if text == 'snooze':
                return snooze_help
            else:
                return """`{}`: List of available commands:

**ack, acknowledge, ok** [message]: *Acknowledge an alert*
**esc, escalate, re-escalate, reescalate, re-esc, reesc** <modification> [message]: *Re-escalate an alert*
**close, done** [message]: *Close an alert*
**open, reopen, re-open** [message]: *Re-open an alert*
**snooze** <duration> [condition]: *Snooze an alert (default 1h) (*`/help_snooze`*)*
any other message: *Comment an alert*

Example: *@{}* **esc** severity = critical *Please check*""".format(display_name, self.bot_name)
        aggregates = self.client.record(['OR', ['IN', ['IN', thread, 'content.threads.root_id'], 'snooze_webhook_responses'], ['IN', ['IN', thread, 'content.multithreads.root_id'], 'snooze_webhook_responses']])
        if len(aggregates) == 0:
            return ':x: `{}`:Cannot find the corresponding alert! (command: `{}`)'.format(display_name, original_message)
        record = aggregates[0]
        action_name = next(action_result.get('action_name') for action_result in record.get('snooze_webhook_responses', [])
            if thread in list(map(lambda x: x.get('root_id'), action_result.get('content', {}).get('threads', []) + action_result.get('content', {}).get('multithreads', [])))) or 'SnoozeBot'
        user = '{} via {}'.format(display_name, action_name)
        if self.snooze_url:
            link = '[[Link]]({}/web/?#/record?tab=All&s=hash%3D{})'.format(self.snooze_url, record['hash'])
            snoozelink = '[[Link]]({}/web/?#/snooze?tab=All&s=hash%3D{})'.format(self.snooze_url, record['hash'])
        if command in ['snooze', '/snooze']:
            LOG.debug("Snooze {} alerts with parameters: '{}'".format(len(aggregates), text))
            duration_match = SnoozeBotPlugin.duration_regex.search(text)
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
                            return ":x: `{}`: Invalid snooze filter duration syntax. Use `/help_snooze` to learn how to use this command".format(display_name)
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
                            return ':x: `{}`: Could not Snooze alert(s)!'.format(display_name)
                        LOG.debug('Done: {}'.format(result))
                        ack_payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': 'Snoozed for {}'.format(duration)} for record in aggregates]
                        self.client.comment_batch(ack_payload)
                        count = ''
                        if len(aggregates) > 1:
                            link = '[[Link]]({}/web/?#/record?tab=Acknowledged)'.format(self.snooze_url)
                            snoozelink = '[[Link]]({}/web/?#/snooze?tab=All)'.format(self.snooze_url)
                            count = '**{}** '.format(len(aggregates))
                        comment_text = ":white_check_mark: {}Alert(s) acknowledged successfully by `{}`! {}\n".format(count, display_name, link)
                        warning_text = ''
                        if len(result['data'].get('added', [])) > 0:
                            res_cond = result['data']['added'][0].get('condition', [])
                            if len(res_cond) > 0 and res_cond[0] == 'SEARCH':
                                warning_text = "\n:warning: Snooze filter condition `{}` might not be expected. Please double check in the Web interface".format(res_cond)
                        if later:
                            return comment_text + ':white_check_mark: Snoozed for {}! Expires at **{}** {}'.format(duration, later.strftime(self.date_format), snoozelink) + warning_text
                        else:
                            return comment_text + ':white_check_mark: Snoozed forever! {}'.format(snoozelink) + warning_text
                    else:
                        return ':x: `{}`: Cannot Snooze more than {} alert(s) without using an explicit condition. Please try again or use [SnoozeWeb]({}/web/?#/snooze).'.format(display_name, self.snooze_limit, self.snooze_url)
                except Exception as e:
                    LOG.exception(e)
                    return ':x: `{}`: Could not Snooze alert(s)!'.format(display_name)
            else:
                return "`{}`: Invalid Snooze filter syntax. Use `/help_snooze` to learn how to use this command".format(display_name)
        elif command in ['ack', 'acknowledge', 'ok', '/ack']:
            LOG.debug('ACK {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return ':white_check_mark: Alert acknowledged successfully by `{}`{}! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** alerts acknowledged successfully by `{}`{}! [[Link]]({}/web/?#/record?tab=Acknowledged)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not acknowledge alert(s)!'.format(display_name)
        elif command in ['esc', 'escalate', 're-escalate', 'reescalate', 're-esc', 'reesc', '/esc']:
            LOG.debug('ESC {} alerts'.format(len(aggregates)))
            try:
                modifications, comment = bot_parser(text)
                payload = [{'type': 'esc', 'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': comment, 'modifications': modifications} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if modifications:
                    msg_extra += ' with modification `{}`'.format(modifications)
                if comment:
                    msg_extra += ' {} message `{}`'.format('and' if modifications else 'with', comment)
                if len(aggregates) == 1:
                    return ':white_check_mark: Alert re-escalated successfully by `{}`{}! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** alerts re-escalated successfully by `{}`{}! [[Link]]({}/web/?#/record?tab=Re-escalated)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not re-escalate alert(s)!'.format(display_name)
        elif command in ['close', 'done', '/close']:
            LOG.debug('CLOSE {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'close', 'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return ':white_check_mark: Alert closed successfully by `{}`{}! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** alerts closed successfully by `{}`{}! [[Link]]({}/web/?#/record?tab=Closed)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not close alert(s)!'.format(display_name)
        elif command in ['open', 'reopen', 're-open', '/open']:
            LOG.debug('OPEN {} alerts'.format(len(aggregates)))
            try:
                payload = [{'type': 'open', 'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': text} for record in aggregates]
                self.client.comment_batch(payload)
                msg_extra = ''
                if text:
                    msg_extra = ' with message `{}`'.format(text)
                if len(aggregates) == 1:
                    return ':white_check_mark: Alert re-opened successfully by `{}`{}! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** alerts re-opened successfully by `{}`{}! [SnoozeWeb]({}/web/?#/record?tab=Alerts&s=state=open)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not re-open alert(s)!'.format(display_name)
        else:
            LOG.debug('COMMENT {} alerts'.format(len(aggregates)))
            try:
                msg_extra = ''
                if command in ['/comment']:
                    msg_extra = text
                else:
                    msg_extra = original_message
                payload = [{'record_uid': record['uid'], 'name': user, 'method': 'teams', 'message': msg_extra} for record in aggregates]
                self.client.comment_batch(payload)
                if len(aggregates) == 1:
                    return ':white_check_mark: Comment added successfully by `{}`: `{}`! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** comments added successfully by `{}`: `{}`! [[Link]]({}/web/?#/record)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not comment alert(s)!'.format(display_name)

class AlertRoute():

    def __init__(self, plugin):
        self.plugin = plugin

    def on_post(self, req, resp):
        medias = req.media
        if not isinstance(medias, list):
            medias = [medias]
        response = self.plugin.process_records(req, medias)
        LOG.debug("Response: {}".format(response))
        resp.status = falcon.HTTP_200
        if response:
            resp.content_type = falcon.MEDIA_JSON
            resp.media = response

class TeamsPlugin(SnoozeBotPlugin):

    def on_alert(self, request, medias):
        response = self.process_alert(request, medias)

    def send_message(self, message, channel_id="", thread={}, attachment={}, request={}):
        data = self.format_message(message, thread)
        LOG.debug('Posting on {}'.format(channel_id))
        props = {}
        thread_id = ''
        if thread:
            thread_id = '/{}/replies'.format(thread['thread_id'])
        #if attachment and request:
        #    props= {'attachments': [{'actions': [{'name': button.get('text'), 'style':  button.get('style', 'default'), 'integration': {'url': '{}://{}/action'.format(request.scheme, get_ip()+':'+str(self.port) if request.host.split(':')[0] in ['127.0.0.1', 'localhost'] else request.host), 'context': {'action': button.get('action')}}} for button in attachment]}]}
        for n in range(3):
            try:
                resp = self.driver.con.post('https://graph.microsoft.com/beta/{}@thread.tacv2/messages{}'.format(channel_id, thread_id), data=data)
                return resp.json()
            except Exception as e:
                LOG.exception(e)
                time.sleep(1)
                continue
        return None

    def serve(self):
        self.app_id = self.config.get('app_id')
        self.app = falcon.App()
        self.app.add_route('/alert', AlertRoute(self))
        wsgi_options = Adjustments(host=self.address, port=self.port)
        httpd = TcpWSGIServer(self.app, adj=wsgi_options)
        LOG.info("Serving on port {}...".format(str(self.port)))
        httpd.run()

    def format_message(self, message, thread):
        uid = uuid.uuid4().hex
        website = self.snooze_url
        one_message = message
        if len(message.get('messages', [])) == 1:
            one_message = message['messages'][0]['msg']
        from_message = ''
        if one_message.get('from'):
            from_message = 'From **{}**'.format(one_message.get('from'))
            if one_message.get('from_msg'):
                from_message += ': {}'.format(one_message.get('from_msg'))
        if not 'messages' in message:
            simple_message = from_message + '<br>'
            if message.get('reply'):
                simple_message += SnoozeBotPlugin.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message.get('reply'))
            else:
                record = message['record']
                timestamp = SnoozeBotPlugin.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', str(datetime.now().astimezone())))
                msg = parse_emoji("::warning:: <b>New escalation</b> on {} ::warning::".format(timestamp))
                if len(record.get('message', '')) > 0:
                    msg += '<br>{}'.format(record.get('message'))
                simple_message += msg
            return {'body': {'content': simple_message, "contentType": "html"}}
        if message.get('header'):
            header = parse_emoji('::warning:: Received {} alerts ::warning::'.format(len(message['messages'])))
        else:
            header = parse_emoji('::warning:: Received alert ::warning::')
        footer_msg = ''
        if message.get('footer'):
            footer_msg = 'Check all alerts in [Snoozeweb]({}/web)'.format(website)
        elif len(message['messages']) == 1:
            footer_msg = message['messages'][0]['msg']['record'].get('message', 'No message')
        footer = Template(""",{
                        "type": "TextBlock",
                        "text": "$footer_msg",
                        "wrap": true
                    }""").substitute({'footer_msg': footer_msg})
        timestamp = SnoozeBotPlugin.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message['messages'][0]['msg']['record'].get('timestamp', datetime.now().astimezone()))
        if len(message['messages']) == 1:
            record = message['messages'][0]['msg']['record']
            facts_list = [('Host', '[{}]({}/web/?#/record?tab=All&s=hash%3D{})'.format(record.get('host', 'Unknown'), website, record.get('hash'))), ('Source', record.get('source', 'Unknown')), ('Process', record.get('process', 'Unknown')), ('Severity', record.get('severity', 'Unknown'))]
            facts = ','.join([Template('{"title": "$key", "value": "$value"}').substitute({'key': key, 'value': value}) for key, value in facts_list])
        else:
            messages = []
            for message in message['messages']:
                if message['msg'].get('record'):
                    msg = {}
                    msg['key'] = '[{}]({}/web/?#/record?tab=All&s=hash%3D{})'.format(message['msg']['record'].get('host', 'Unknown'), website, message['msg']['record'].get('hash'))
                    if message['msg'].get('threads'):
                        msg['key'] += ' (e)'
                    msg['value'] = '[{source}] **{process}** {message}'.format(source=message['msg']['record'].get('source', 'Unknown'), process=message['msg']['record'].get('process', 'Unknown'), message=message['msg']['record'].get('message', ''))
                    if message['msg'].get('from'):
                        from_msg = 'From **{}**'.format(message['msg'].get('from'))
                        if message['msg'].get('from_msg'):
                            from_msg += ': {}'.format(message['msg'].get('from_msg'))
                        msg['value'] += ' ({})'.format(from_msg)
                    messages.append(Template('{"title": "$key", "value": "$value"}').substitute(msg))
            facts = ','.join(messages)
        teamsappid = ''
        card = {
            'body': {
                'contentType': 'html',
                'content': '<attachment id="{}"></attachment>'.format(uid)
            },
            'attachments': [{
                'id': uid,
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'contentUrl': None,
                'content': Template('''{
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "msteams": {
                        "width": "full"
                    },
                    "body": [{
                        "type": "ColumnSet",
                        "columns": [{
                            "type": "Column",
                            "items": [{
                                "type": "TextBlock",
                                "weight": "Bolder",
                                "text": "$header",
                                "wrap": true
                            },{
                                "type": "TextBlock",
                                "spacing": "None",
                                "text": "$timestamp",
                                "isSubtle": true,
                                "wrap": true
                            },{
                                "type": "TextBlock",
                                "spacing": "None",
                                "text": "$from",
                                "wrap": true
                            }],
                            "width": "stretch"
                        }]},{
                            "type": "FactSet",
                            "facts": [$facts]
                        }$footer]
                }''').substitute({'schema': '$schema', 'header': header, 'footer': footer, 'timestamp': timestamp, 'facts': facts, 'from': from_message}),
                'name': "Testing name",
                'thumbnailUrl': None
            }]
        }
        if self.app_id:
            card['attachments'][0]['teamsAppId'] = self.app_id
        return card

class TeamsBot():

    def __init__(self):
        self.snoozebot = SnoozeBot('SNOOZE_TEAMS_PATH', 'teamsbot.yaml', 'TeamsPlugin')
        client_id = self.snoozebot.config.get('client_id')
        client_secret = self.snoozebot.config.get('client_secret')
        tenant_id = self.snoozebot.config.get('tenant_id')
        scopes = ['offline_access', 'ChannelMessage.Send', 'Chat.ReadBasic', 'Team.ReadBasic.All', 'Channel.ReadBasic.All']
        credentials = (client_id, client_secret)
        protocol = MSGraphProtocol(api_version='beta')
        account = Account(credentials, tenant_id=tenant_id, protocol=protocol)
        if not account.is_authenticated:
            account.authenticate(scopes=scopes, redirect_uri='https://localhost')
        self.snoozebot.plugin.driver = account.teams()

def main():
    TeamsBot().snoozebot.plugin.serve()

if __name__ == '__main__':
    main()
