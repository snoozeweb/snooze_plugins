import json
import yaml
import os
import re
import logging
import uuid
import time
import random
import asyncio
import sys
import socket
from datetime import datetime, timedelta
from dateutil import parser
from pathlib import Path
from snooze_client import Snooze
from snooze_mattermostbot.bot_parser import parser as bot_parser
from mmpy_bot import listen_to, listen_webhook
from mmpy_bot import Plugin, Message, WebHookEvent, Bot, Settings, ActionEvent
from mmpy_bot.webhook_server import handle_json_error, NoResponse
from aiohttp import web

LOG = logging.getLogger("snooze.mattermostchat")

class MattermostBot():

    date_regex = re.compile(r"[0-9]{1,4}-[0-9]{1,2}-[0-9]{1,2}T[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}[\+\d]*")
    duration_regex = re.compile(r"((\d+) *(mins|min|m|hours|hour|h|weeks|week|w|days|day|d|months|month|years|year|y)|forever){0,1} *(.*)", re.IGNORECASE)

    def __init__(self):
        self.load_config()
        level = logging.INFO
        if self.config.get('debug', False):
            level = logging.DEBUG
        logformat = "%(asctime)s - %(name)s: %(levelname)s - %(message)s"
        self.address = self.config.get('listening_address', '0.0.0.0')
        self.port = self.config.get('listening_port', 5202)
        self.mattermost_url = self.config.get('mattermost_url', 'http://localhost')
        self.mattermost_port = self.config.get('mattermost_port', 8065)
        self.bot_token = self.config.get('bot_token', 'jdd76efzcpn63rp9ocpi3xysew')
        self.ssl_verify = self.config.get('ssl_verify', False)
        self.bot = Bot(
            settings=Settings(
                MATTERMOST_URL = self.mattermost_url,
                MATTERMOST_PORT = self.mattermost_port,
                BOT_TOKEN = self.bot_token,
                SSL_VERIFY = self.ssl_verify,
                WEBHOOK_HOST_ENABLED = True,
                WEBHOOK_HOST_URL = self.address,
                WEBHOOK_HOST_PORT = self.port,
                DEBUG = self.config.get('debug', False),
            ),
            plugins=[MattermostPlugin(self.config)],
        )
        logging.getLogger("").handlers.clear()
        logging.basicConfig(format=logformat, level=level)

        self.bot.webhook_server.app.add_routes([web.post("/{webhook_id}", self.json_webhook), web.post("/command/{webhook_id}", self.form_webhook)])
        try:
            self.bot.run()
        except KeyboardInterrupt:
            pass
        except:
            LOG.exception(e)

    def load_config(self):
        config_path = Path(os.environ.get('SNOOZE_MATTERMOSTBOT_PATH', '/etc/snooze'))
        config_file = config_path / 'mattermostbot.yaml'
        if config_file.exists():
            self.config = yaml.safe_load(config_file.read_text())
        else:
            self.config = {}

    async def form_webhook(self, request: web.Request):
        data = await request.post()
        return await self.webhook(request, data)

    @handle_json_error
    async def json_webhook(self, request: web.Request):
        data = await request.json()
        return await self.webhook(request, data)

    async def webhook(self, request: web.Request, data):
        webhook_id = request.match_info.get("webhook_id", "")
        if type(data) is dict and "trigger_id" in data:
            # Use the trigger ID to identify this request
            event = ReqActionEvent(
                request,
                data,
                request_id=data["trigger_id"],
                webhook_id=webhook_id,
            )
        else:
            # Generate an ID based on the current time and a random number.
            event = ReqWebHookEvent(
                request,
                data,
                request_id=f"{time.time()}_{random.randint(0, 10000)}",
                webhook_id=webhook_id,
            )
        self.bot.webhook_server.event_queue.put(event)

        # Register a Future object that will signal us when a response has arrived,
        # and wait for it to complete.
        await_response = asyncio.get_event_loop().create_future()
        self.bot.webhook_server.response_handlers[event.request_id] = await_response
        await await_response

        result = await_response.result()
        if result is NoResponse:
            return web.Response(status=200)

        return web.json_response(result)

class ReqActionEvent(ActionEvent):

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

class ReqWebHookEvent(WebHookEvent):

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

class MattermostPlugin(Plugin):

    def __init__(self, config):
        super(MattermostPlugin, self).__init__()
        self.config = config
        self.date_format = self.config.get('date_format', '%a, %b %d, %Y at %I:%M %p')
        self.client = Snooze()
        self.bot_name = self.config.get('bot_name', 'Bot')
        self.snooze_url = self.config.get('snooze_url', 'http://localhost:5201')
        if self.snooze_url.endswith('/'):
            self.snooze_url = self.snooze_url[:-1]
        self.message_limit = self.config.get('message_limit', 10)
        self.snooze_limit = self.config.get('snooze_limit', self.message_limit)

    @listen_to("", needs_mention=True)
    async def on_user_message(self, message: Message):
        return_msg = self.process_user_message(message)
        self.send_message(return_msg, thread={'channel_id': message.channel_id, 'root_id': message.root_id or message.id})

    @listen_webhook("slash")
    async def on_slash_command(self, event: ReqWebHookEvent):
        return_msg = self.process_user_message(event)
        #return_msg = "Not Implemented"
        self.driver.respond_to_web(event, {"response_type": "in_channel", "text": return_msg})

    @listen_webhook("action")
    async def on_button_clicked(self, event: ReqActionEvent):
        event.text = event.context.get('action')
        event.root_id = self.driver.get_thread(event.post_id).get('order',[event.post_id])[0]
        return_msg = self.process_user_message(event)
        self.send_message(return_msg, thread={'channel_id': event.channel_id, 'root_id': event.root_id})

    @listen_webhook("alert")
    async def on_alert(self, event: ReqWebHookEvent):
        medias = event.body
        if not isinstance(medias, list):
            medias = [medias]
        response = self.process_records(event.request, medias)
        LOG.debug("Response: {}".format(response))
        self.driver.respond_to_web(event, response)

    def send_message(self, message, channel_id="", thread={}, attachment={}, request={}):
        LOG.debug('Posting on {} msg {}'.format(channel_id, message))
        root_id = ''
        props = {}
        if thread:
            channel_id = thread['channel_id']
            root_id = thread['root_id']
        if attachment and request:
            props= {'attachments': [{'actions': [{'name': button.get('text'), 'style':  button.get('style', 'default'), 'integration': {'url': '{}://{}/action'.format(request.scheme, get_ip()+':'+str(self.config.get('listening_port', 5202)) if request.host.split(':')[0] in ['127.0.0.1', 'localhost'] else request.host), 'context': {'action': button.get('action')}}} for button in attachment]}]}
        for n in range(3):
            try:
                resp = self.driver.create_post(channel_id, message, root_id=root_id, props=props)
                return resp
            except Exception as e:
                LOG.exception(e)
                time.sleep(1)
                continue
        return None

    def process_records(self, req, medias):
        multi = len(medias) > 1
        channels = {}
        header = ''
        footer = ''
        website = ''
        return_value = {}
        website = self.snooze_url
        action_name = req.query.get('snooze_action_name', 'unknown_action')
        for req_media in medias[:self.message_limit]:
            self.process_rec(channels, req_media, action_name, multi, website)
        for req_media in medias[self.message_limit:]:
            self.process_rec(channels, req_media, action_name, multi, website, False)
        for channel, content in channels.items():
            if multi:
                timestamp = datetime.now().astimezone().strftime(self.date_format)
                header = ':warning: Received **{}** alerts on {} :warning:\n\n'.format(len(content), timestamp)
                if len(content) > self.message_limit:
                    footer = '\n...\n\nCheck all alerts in [Snoozeweb]({}/web)'.format(website)
            attachment = [{'text': 'Acknowledge', 'action': 'ack', 'style': 'success'}, {'text': 'Close', 'action': 'close', 'style': 'primary'}]
            if not multi and content[0]['threads']:
                for thread in content[0]['threads']:
                    self.send_message(content[0]['msg'], thread=thread, attachment=attachment, request=req)
                return_value = {content[0]['record_hash']: {'threads': content[0]['threads'], 'multithreads': content[0]['multithreads']}}
            else:
                resp = self.send_message(header + '\n'.join([message['msg'] for message in content if len(message['msg']) > 0]) + footer, channel_id=channel, attachment=attachment, request=req)
                for message in content:
                    t = {'channel_id': channel, 'root_id': resp['root_id'] or resp['id']}
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
        msg = ''
        threads = next((action_result.get('content', {}).get('threads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        multithreads = next((action_result.get('content', {}).get('multithreads', []) for action_result in record.get('snooze_webhook_responses', []) if action_result.get('action_name') == action_name), [])
        if process:
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
                    msg += MattermostBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), reply)
                elif message:
                    msg += ":warning: **New escalation** :warning:\n" + message
                else:
                    timestamp = MattermostBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', str(datetime.now().astimezone().strftime(self.date_format))))
                    msg += ":warning: **New escalation** :warning:\n**Date:** {}".format(timestamp)
            else:
                if multi:
                    if threads:
                        msg += '**[Esc]** '
                    if message_group:
                        msg += MattermostBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message_group)
                    else:
                        msg += "[{source}] [{host}]({website}/web/?#/record?tab=All&s=hash%3D{rhash}) `{process}` {message}".format(source=record.get('source', 'Unknown'), website=website, rhash=record.get('hash'), host=record.get('host', 'Unknown'), process=record.get('process', 'Unknown'), message=record.get('message', 'No message'))
                else:
                    if message:
                        msg += MattermostBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), message)
                    else:
                        timestamp = MattermostBot.date_regex.sub(lambda m: parser.parse(m.group()).strftime(self.date_format), record.get('timestamp', datetime.now().astimezone().strftime(self.date_format)))
                        msg += "**Date:** {timestamp}\n**Host:** {host}\n**Source:** {source}\n**Process:** {process}\n**Severity:** {severity}\n**URL:** [Snooze]({website}/web/?#/record?tab=All&s=hash%3D{rhash})\n**Message:** {message}".format(timestamp=timestamp, host=record.get('host', 'Unknown'), source=record.get('source', 'Unknown'), process=record.get('process', 'Unknown'), severity=record.get('severity', 'Unknown'), website=website, rhash=record.get('hash'), message=record.get('message', 'No message'))
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
            if thread in list(map(lambda x: x.get('root_id'), action_result.get('content', {}).get('threads', []) + action_result.get('content', {}).get('multithreads', [])))) or 'MattermostBot'
        user = '{} via {}'.format(display_name, action_name)
        if self.snooze_url:
            link = '[[Link]]({}/web/?#/record?tab=All&s=hash%3D{})'.format(self.snooze_url, record['hash'])
            snoozelink = '[[Link]]({}/web/?#/snooze?tab=All&s=hash%3D{})'.format(self.snooze_url, record['hash'])
        if command in ['snooze', '/snooze']:
            LOG.debug("Snooze {} alerts with parameters: '{}'".format(len(aggregates), text))
            duration_match = MattermostBot.duration_regex.search(text)
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
                        ack_payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': 'Snoozed for {}'.format(duration)} for record in aggregates]
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
                payload = [{'type': 'ack', 'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': text} for record in aggregates]
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
                payload = [{'type': 'esc', 'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': comment, 'modifications': modifications} for record in aggregates]
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
                payload = [{'type': 'close', 'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': text} for record in aggregates]
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
                payload = [{'type': 'open', 'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': text} for record in aggregates]
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
                payload = [{'record_uid': record['uid'], 'name': user, 'method': 'mattermost', 'message': msg_extra} for record in aggregates]
                self.client.comment_batch(payload)
                if len(aggregates) == 1:
                    return ':white_check_mark: Comment added successfully by `{}`: `{}`! {}'.format(display_name, msg_extra, link)
                else:
                    return ':white_check_mark: **{}** comments added successfully by `{}`: `{}`! [[Link]]({}/web/?#/record)'.format(len(aggregates), display_name, msg_extra, self.snooze_url)
            except Exception as e:
                LOG.exception(e)
                return ':x: `{}`: Could not comment alert(s)!'.format(display_name)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    MattermostBot()

if __name__ == '__main__':
    main()
