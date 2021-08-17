'''SMTP listener for snooze'''

import asyncore
import email
import email.policy
import logging
import re

from dateutil import parser
from smtpd import SMTPServer

from snooze_smtp.parser import parse_received
from snooze_client import Snooze

LOG = logging.getLogger("snooze.smtp")
logging.basicConfig(format="%(name)s: %(levelname)s - %(message)s", level=logging.DEBUG)

class SnoozeSMTPServer(SMTPServer):
    def __init__(self, domains, *args, **kwargs):
        LOG.info("Starting SMTP server...")
        self.snooze = Snooze()
        self.domains = domains
        super().__init__(*args, **kwargs)

    @staticmethod
    def guess_severity(subject):
        '''Guess the severity of the mail by looking at the subject'''
        keywords = [
            'fatal',
            'critical',
            'warning',
            'error',
            'notice',
            'info',
            'success',
            'ok',
        ]
        for keyword in keywords:
            if re.search(r"\b%s\b" % keyword, subject, re.IGNORECASE):
                LOG.debug("Guessed the severity %s from subject '%s'", keyword, subject)
                return keyword

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        '''Method called every time an email is received'''
        LOG.debug("Received mail from %s", mailfrom)
        mail = email.message_from_bytes(data, policy=email.policy.SMTPUTF8)
        record = dict(mail)
        user, host = record['From'].split('@', 1)
        shortname, domain = host.split('.', 1)
        if domain in self.domains:
            record['host'] = shortname
            record['fqdn'] = host
        else:
            record['host'] = host

        # Received field
        relays = []
        for relay in mail.get_all('Received'):
            parsed_relay = parse_received(relay)
            if parsed_relay:
                relays.append(parsed_relay)
        if relays:
            record['relays'] = relays

        record['user'] = user
        record['message'] = record['Subject']
        plain = mail.get_body(preferencelist=('plain',))
        if plain:
            record['message_plain'] = plain.get_content()
        html = mail.get_body(preferencelist=('html',))
        if html:
            record['message_html'] = html.get_content()
        timestamp = parser.parse(record['Date'])
        record['timestamp'] = timestamp.isoformat()
        record['source'] = 'smtp'
        record['smtp_peer'] = peer
        record['smtp_mailfrom'] = mailfrom
        record['smtp_rcpttos'] = rcpttos
        record['process'] = user

        severity = self.guess_severity(record['Subject'])
        if severity:
            record['severity'] = severity
        else:
            record['severity'] = 'info'

        LOG.debug("Will send alert to snooze: %s", record)
        self.snooze.alert(record)
        LOG.debug("Successfully sent message to snooze")

def main():
    '''Main loop'''
    SnoozeSMTPServer(['dc.odx.co.jp'], ('0.0.0.0', 1025), None)
    try:
        asyncore.loop()
    except Exception as err:
        print("Exception during loop: %s" % err)

if __name__ == '__main__':
    main()
