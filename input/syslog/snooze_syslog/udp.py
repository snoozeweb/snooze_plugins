'''UDP handler'''

from logging import getLogger
from threading import Thread
from socketserver import DatagramRequestHandler, UDPServer

LOG = getLogger("snooze.syslog.udp")

class UDPHandler(DatagramRequestHandler):
    '''Handler for UDPServer'''
    def handle(self):
        queue = self.server.queue
        client_addr = self.client_address[0].encode().decode()
        for line in self.rfile:
            LOG.debug("Received from %s: %s", client_addr, line)
            queue.put((client_addr, line))

class UDPListener(Thread):
    '''Wrap the UDP server into a stoppable process'''
    def __init__(self, host, port, queue):
        self.server = UDPServer((host, port), UDPHandler)
        self.server.queue = queue
        Thread.__init__(self)

    def run(self):
        '''Start the UDP listener'''
        LOG.info("Starting UDP listener")
        self.server.serve_forever()

    def stop(self):
        '''Stop the UDP listener'''
        LOG.info("Stopping UDP listener")
        self.server.shutdown()
