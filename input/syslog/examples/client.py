#!/usr/bin/env python
'''Testing the server by sending logs'''

from pysyslogclient import SyslogClientRFC5424, SyslogClientRFC3164

def test_tcp_rfc3164():
    client1 = SyslogClientRFC3164('127.0.0.1', 1514, proto='TCP')
    client1.log('My message', program='myapp')
    client1.close()

def test_tcp_rfc5424():
    client2 = SyslogClientRFC5424('127.0.0.1', 1514, proto='TCP')
    client2.log('My message', program='myapp')
    client2.close()

if __name__ == '__main__':
    test_tcp_rfc3164()
    test_tcp_rfc5424()
