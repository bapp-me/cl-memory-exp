"""Unprivileged-content TCP relay, with no credentials or model logic."""
import argparse
import socket
import socketserver
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--bind', required=True); parser.add_argument('--port', type=int, required=True)
parser.add_argument('--target', required=True); parser.add_argument('--target-port', type=int, required=True)
args = parser.parse_args()


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.create_connection((args.target, args.target_port), timeout=30) as remote:
            remote.settimeout(None)
            def copy(source, target):
                try:
                    while data := source.recv(65536): target.sendall(data)
                except OSError: pass
                finally:
                    try: target.shutdown(socket.SHUT_WR)
                    except OSError: pass
            worker = threading.Thread(target=copy, args=(self.request, remote))
            worker.start(); copy(remote, self.request); worker.join()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server((args.bind, args.port), Handler) as server:
    print('Internal agent relay ready.', flush=True)
    server.serve_forever()
