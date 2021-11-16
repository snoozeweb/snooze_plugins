from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage

from snooze_smtp.main import make_record

class TestMakeRecord:
    def test_make_basic(self):
        mail = EmailMessage()
        mail['Subject'] = 'Warning: job failure on myhost01.example.com'
        mail['From'] = 'myapp@example.com'
        mail['To'] = 'root@example.com'
        text = MIMEText('''Test plain text message''', 'plain')
        mail.attach(text)
        peer = ['10.0.0.10', 12345]
        mailfrom = 'myapp@myhost01.example.com'
        rcpttos = ['root@example.com']
        domains = ['example.com']
        record = make_record(mail, peer, mailfrom, rcpttos, domains)
        assert record['host'] == 'myhost01'
        assert record['fqdn'] == 'myhost01.example.com'
        assert record['process'] == 'myapp'
        assert record['message'] == 'Warning: job failure on myhost01.example.com'
        assert record['severity'] == 'warning'

    def test_display_names(self):
        mail = EmailMessage()
        mail['Subject'] = 'Warning: job failure on myhost01.example.com'
        mail['From'] = '"My Application" <myapp@example.com>'
        mail['To'] = '"Root" <root@example.com>'
        text = MIMEText('''Test plain text message''', 'plain')
        mail.attach(text)
        peer = ['10.0.0.10', 12345]
        mailfrom = 'myapp@myhost01.example.com'
        rcpttos = ['root@example.com']
        domains = ['example.com']
        record = make_record(mail, peer, mailfrom, rcpttos, domains)
        assert record['smtp']['from'] == {'display': 'My Application', 'mail': 'myapp@example.com'}
        assert record['smtp']['to'] == [{'display': 'Root', 'mail': 'root@example.com'}]
