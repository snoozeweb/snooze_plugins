'''SMTP listener for snooze'''

import asyncore
import email
import email.policy
import logging
import re

from dateutil import parser
from datetime import datetime
from smtpd import SMTPServer

from snooze_smtp.parser import parse_received
from snooze_client import Snooze

LOG = logging.getLogger("snooze.smtp")
logging.basicConfig(format="%(name)s: %(levelname)s - %(message)s", level=logging.DEBUG)

def make_record(mail, peer, mailfrom, rcpttos, domains):
    '''
    Create a snooze record from a mail and its SMTP reception data.
    '''
    record = {}
    smtp = {}
    record['smtp'] = smtp
    smtp['header'] = dict(mail)
    smtp['peer'] = peer
    smtp['mailfrom'] = mailfrom
    smtp['rcpttos'] = rcpttos

    # If the parsing fails, it returns ('', '')
    display_from, real_from = email.utils.parseaddr(mail.get('From', ''))
    smtp['from'] = {'display': display_from, 'mail': real_from}

    # Computing display_names and real names
    for key in ['to', 'cc', 'resent-to', 'resent-cc']:
        array = []
        for recp in mail.get_all(key, []):
            display_name, addr = email.utils.parseaddr(recp)
            array.append({'display': display_name, 'mail': addr})
        smtp[key] = array

    # Detecting the application user that sent the mail
    user, host = mailfrom.split('@', 1)
    smtp['user'] = user

    # Shortname/FQDN
    shortname, domain = host.split('.', 1)
    if domain in domains:
        record['host'] = shortname
        record['fqdn'] = host
    else:
        record['host'] = host

    # Received field
    smtp['relays'] = list(map(parse_received, mail.get_all('Received', [])))

    record['message'] = mail['Subject']
    body = {}
    smtp['body'] = body

    for content_type in ['plain', 'html']:
        data = mail.get_body(preferencelist=(content_type,))
        if data:
            body[content_type] = data.get_content()

    if mail.get('Date'):
        timestamp = parser.parse(mail['Date'])
    else:
        timestamp = datetime.now()
    record['timestamp'] = timestamp.isoformat()
    record['source'] = 'smtp'
    record['process'] = user

    severity = guess_severity(mail['Subject'])
    if severity:
        record['severity'] = severity
    else:
        record['severity'] = 'err'

    return record

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
    else:
        return None

class SnoozeSMTPServer(SMTPServer):
    def __init__(self, domains, *args, **kwargs):
        LOG.info("Starting SMTP server...")
        self.snooze = Snooze()
        self.domains = domains
        super().__init__(*args, **kwargs)

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        '''Method called every time an email is received'''
        try:
            LOG.debug("Received mail from %s", mailfrom)
            mail = email.message_from_bytes(data, policy=email.policy.SMTPUTF8)

            record = make_record(mail, peer, mailfrom, rcpttos, self.domains)

            LOG.debug("Will send alert to snooze: %s", record)
            self.snooze.alert(record)
            LOG.debug("Successfully sent message to snooze")
            return None
        except Exception as err:
            LOG.error(err)
            return None

def main():
    '''Main loop'''
    SnoozeSMTPServer(['dc.odx.co.jp'], ('0.0.0.0', 1025), None)
    try:
        asyncore.loop()
    except Exception as err:
        print("Exception during loop: %s" % err)

if __name__ == '__main__':
    main()
