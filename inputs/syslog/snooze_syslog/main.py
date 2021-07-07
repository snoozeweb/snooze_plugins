import logging
import os
import platform
import ssl
import sys
import yaml

from multiprocessing import JoinableQueue, Process
from multiprocessing.pool import ThreadPool as Pool
from socketserver import TCPServer, ThreadingMixIn, StreamRequestHandler, DatagramRequestHandler, UDPServer
from threading import Thread
from pathlib import Path

from snooze_client import Snooze
from snooze_syslog.parser import parse_syslog

LOG = logging.getLogger("snooze.syslog")
logging.basicConfig(format="%(asctime)s - %(name)s: %(levelname)s - %(message)s", level=logging.DEBUG)

class ThreadedTCPServer(ThreadingMixIn, TCPServer, object):
    '''Multi-threaded TCPServer'''
    def __init__(self, queue, config, address, requestHandlerClass):
        self.queue = queue
        self.config = config
        LOG.debug("Starting mutlithreaded TCP receiver")
        TCPServer.__init__(self, address, requestHandlerClass, bind_and_activate=True)

    def get_request(self):
        if self.config.get('ssl'):
            (socket, addr) = TCPServer.get_request(self)
            ssl_socket = ssl.wrap_socket(
                socket,
                server_side=True,
                certfile=self.config.get('certfile'),
                keyfile=self.config.get('keyfile'),
            )
            return (ssl_socket, addr)
        else:
            return TCPServer.get_request(self)

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self)

    def server_close(self):
        self.socket.close()
        self.shutdown()
        return TCPServer.server_close(self)

class UDPHandler(DatagramRequestHandler):
    '''Handler for UDPServer'''
    def handle(self):
        queue = self.server.queue
        client_addr = self.client_address[0].encode().decode()
        for line in self.rfile:
            LOG.debug(f"[udp] Received from {client_addr}: {line}")
            queue.put((client_addr, line))

class QueuedTCPRequestHandler(StreamRequestHandler):
    '''Handler for TCPServer'''
    def __init__(self, request, client_address, server):
        self.queue = server.queue
        LOG.debug("Starting QueuedTCPRequestHandler")
        StreamRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        client_addr = self.client_address[0].encode().decode()
        for line in self.rfile:
            LOG.debug(f"[tcp] Received from {client_addr}: {line}")
            self.queue.put((client_addr, line))

    def finish(self):
        self.request.close()

class SyslogDaemon(object):
    def __init__(self):
        self.parse_queue = JoinableQueue()
        self.send_queue = JoinableQueue()

        self.config = {}

        config_file = os.environ.get('SNOOZE_SYSLOG_CONFIG') or '/etc/snooze/syslog.yaml'
        config_file = Path(config_file)
        try:
            with config_file.open('r') as myfile:
                self.config = yaml.safe_load(myfile.read())
        except Exception as err:
            LOG.error("Error loading config: %s", err)

        if not isinstance(self.config, dict):
            self.config = {}

        # Config and defaults
        snooze_uri = self.config.get('snooze_server')
        self.api = Snooze(snooze_uri)

        parse_workers_pool = self.config.get('parse_workers', 4)
        send_workers_pool = self.config.get('send_workers', 4)

        self.listening_address = self.config.get('listening_address', '0.0.0.0')
        self.listening_port = self.config.get('listening_port', 1514)

        self.tcp_server = ThreadedTCPServer(
            self.parse_queue,
            self.config,
            (self.listening_address, self.listening_port),
            QueuedTCPRequestHandler,
        )
        self.udp_server = UDPServer(
            (self.listening_address, self.listening_port),
            UDPHandler,
        )
        self.udp_server.queue = self.parse_queue

        tcp_thread = Thread(target=self.tcp_server.serve_forever)
        udp_thread = Thread(target=self.udp_server.serve_forever)

        try:
            tcp_thread.start()
            udp_thread.start()
            parse_threads = self.start_parse_workers(parse_workers_pool)
            send_threads = self.start_send_workers(send_workers_pool)

            all_threads = [tcp_thread, udp_thread] + parse_threads + send_threads

            for thread in all_threads:
                thread.join()

        finally:
            LOG.info("Stopping TCP socket...")
            self.tcp_server.shutdown()
            LOG.info("Stopping TCP server thread...")
            tcp_thread.join()
            LOG.info("Stopping UDP socket...")
            self.udp_server.shutdown()
            LOG.info("Stopping UDP server thread...")
            udp_thread.join()
            LOG.info("Stopping parse workers...")
            self.stop_threads(self.parse_queue, parse_threads)
            LOG.info("Stopping send workers...")
            self.stop_threads(self.send_queue, send_threads)

    def start_parse_workers(self, worker_pool):
        threads = []
        for index in range(worker_pool):
            mythread = Thread(target=self.parse_worker, args=(index,))
            mythread.start()
            threads.append(mythread)
        return threads

    def start_send_workers(self, worker_pool):
        threads = []
        for index in range(worker_pool):
            mythread = Thread(target=self.send_worker, args=(index,))
            mythread.start()
            threads.append(mythread)
        return threads

    def parse_worker(self, index):
        '''A worker for parsing syslog syntax'''
        while True:
            args = self.parse_queue.get()
            if not args:
                LOG.info(f"Stopping parse worker {index}")
                break
            record = parse_syslog(*args)
            self.send_queue.put(record)

    def send_worker(self, index):
        '''A worker for sending records to Snooze'''
        while True:
            LOG.debug("[send_record] Waiting for queue")
            records = self.send_queue.get()
            if not records:
                LOG.info(f"Stopping send worker {index}")
                break
            for record in records:
                LOG.debug(f"Sending record to snooze: {record}")
                self.api.alert(record)

    def stop_threads(self, queue, threads):
        for _ in threads:
            queue.put(None)
        for thread in threads:
            thread.join()

def main():
    LOG = logging.getLogger("snooze.syslog")
    try:
        LOG.info("Starting snooze syslog daemon")
        SyslogDaemon()
    except (SystemExit, KeyboardInterrupt):
        LOG.info("Exiting snooze syslog daemon")
        sys.exit(0)
    except Exception as e:
        LOG.error(e, exc_info=1)
        sys.exit(1)

if __name__ == '__main__':
    main()
