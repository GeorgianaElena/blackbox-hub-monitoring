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
from jupyterhub.utils import url_path_join
import requests

CHECK_COMPLETED = Gauge(
    "check_completed", "whether or not hubtraf-check completed successfully"
)

from jupyterhub.services.auth import HubAuthenticated


class HubMetricsHandler(HubAuthenticated, RequestHandler):
    def initialize(self, args, registry=REGISTRY):
        self.args = args
        self.registry = registry

    @authenticated
    async def get(self):
        args = self.args

        out = subprocess.check_output(["hubtraf-check", args.hub_url, args.username])
        print(out)

        encoder, content_type = exposition.choose_encoder(
            self.request.headers.get("Accept")
        )
        self.set_header("Content-Type", content_type)
        self.write(encoder(self.registry))


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "hub_url", help="Hub URL to send traffic to (without a trailing /)"
    )
    argparser.add_argument("username", help="Name of the user")
    args = argparser.parse_args()

    api_token = os.environ["JUPYTERHUB_API_TOKEN"]
    api_url = os.environ["JUPYTERHUB_API_URL"]

    # Request a token for the user
    token_request_url = url_path_join(api_url, "/users/monitor/tokens")
    resp = requests.post(
        token_request_url, headers={"Authorization": f"token {api_token}"}
    )
    user_token = resp.json()["token"]
    os.environ["JUPYTERHUB_API_TOKEN"] = user_token

    app = Application(
        [
            (
                os.environ["JUPYTERHUB_SERVICE_PREFIX"] + "/?",
                HubMetricsHandler,
                {"args": args},
            ),
            (r".*", HubMetricsHandler, {"args": args}),
        ]
    )

    http_server = HTTPServer(app)
    url = urlparse(os.environ["JUPYTERHUB_SERVICE_URL"])

    http_server.listen(url.port, url.hostname)

    IOLoop.current().start()


if __name__ == "__main__":
    main()
