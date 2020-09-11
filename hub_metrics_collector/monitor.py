import argparse
import os
import subprocess
from urllib.parse import urlparse

from prometheus_client import Gauge, REGISTRY, exposition
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.web import authenticated
from tornado.web import RequestHandler

SERVER_STARTED = Gauge("server_started", "whether or not the user's server started")

from jupyterhub.services.auth import HubAuthenticated

def get_args():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "hub_url", help="Hub URL to send traffic to (without a trailing /)"
    )
    args = argparser.parse_args()

    return args

class HubMetricsHandler(HubAuthenticated, RequestHandler):
    def initialize(self, registry=REGISTRY):
        self.registry = registry

    @authenticated
    async def get(self):
        args = get_args()
        subprocess.check_output([
            "hubtraf-check",
            args.hub_url,
            os.environ['JUPYTERHUB_SERVICE_NAME'],
        ])

        encoder, content_type = exposition.choose_encoder(self.request.headers.get('Accept'))
        self.set_header('Content-Type', content_type)
        self.write(encoder(self.registry))


def main():
    app = Application(
        [
            (os.environ['JUPYTERHUB_SERVICE_PREFIX'] + '/?', HubMetricsHandler),
            (r'.*', HubMetricsHandler),
        ]
    )

    http_server = HTTPServer(app)
    url = urlparse(os.environ['JUPYTERHUB_SERVICE_URL'])

    http_server.listen(url.port, url.hostname)

    IOLoop.current().start()


if __name__ == '__main__':
    main()
