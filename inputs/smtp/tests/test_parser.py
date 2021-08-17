from snooze_smtp.parser import parse_received

class TestParseReceived:

    def test_simple(self):
        received = 'by mx.example.com with SMTP id myid123456789; Mon, 16 Aug 2021 23:50:33 -0700 (PDT)'
        relay = parse_received(received)
        assert relay
        assert relay['by'] == 'mx.example.com'
        assert relay['with'] == 'SMTP'
        assert relay['id'] == 'myid123456789'
        assert relay['timestamp'] == '2021-08-16T23:50:33-07:00'

    def test_complete(self):
        received = "from mx01.example.com (mx.example.com. [1.2.3.4])" \
        + "        by mx.example2.com with SMTPS id myid12345" \
        + "        for <john.doe@example3.com>" \
        + "        (Example company 3);" \
        + "        Mon, 16 Aug 2021 08:00:37 -0700 (PDT)"
        relay = parse_received(received)
        assert relay
        assert relay['from'] == 'mx01.example.com'
        assert relay['from_domain'] == 'mx.example.com.'
        assert relay['from_ip'] == '1.2.3.4'
        assert relay['by'] == 'mx.example2.com'
        assert relay['with'] == 'SMTPS'
        assert relay['id'] == 'myid12345'
        assert relay['timestamp'] == '2021-08-16T08:00:37-07:00'

    def test_complete_newline(self):
        received = "from mx01.example.com (mx.example.com. [1.2.3.4])\n" \
        + "        by mx.example2.com with SMTPS id myid12345\n" \
        + "        for <john.doe@example3.com>\n" \
        + "        (Example company 3);\n" \
        + "        Mon, 16 Aug 2021 08:00:37 -0700 (PDT)"
        relay = parse_received(received)
        assert relay
        assert relay['from'] == 'mx01.example.com'
        assert relay['from_domain'] == 'mx.example.com.'
        assert relay['from_ip'] == '1.2.3.4'
        assert relay['by'] == 'mx.example2.com'
        assert relay['with'] == 'SMTPS'
        assert relay['id'] == 'myid12345'
        assert relay['timestamp'] == '2021-08-16T08:00:37-07:00'
