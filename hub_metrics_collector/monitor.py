import argparse
from contextlib import redirect_stdout
from enum import Enum
import io
import os
from urllib.parse import urlparse

from hubtraf.check import check_user
from jupyterhub.services.auth import HubAuthenticated
from jupyterhub.utils import url_path_join
import json
from prometheus_client import Gauge, Histogram, REGISTRY, exposition
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.web import authenticated
from tornado.web import RequestHandler
import requests


CHECK_COMPLETED = Gauge(
    "check_completed", "whether or not hubtraf-check completed successfully"
)
SERVER_START_DURATION_SECONDS = Histogram(
    "server_start_duration_seconds", "Time taken to start the user server", ["status"]
)
KERNEL_START_DURATION_SECONDS = Histogram(
    "kernel_start_duration_seconds", "Time taken to start the kernel", ["status"]
)
CODE_EXECUTE_DURATION_SECONDS = Histogram(
    "code_execute_duration_seconds",
    "Time taken to execute some simple code",
    ["status"],
)
KERNEL_STOP_DURATION_SECONDS = Histogram(
    "kernel_stop_duration_seconds", "Time taken to stop the kernel", ["status"]
)
SERVER_STOP_DURATION_SECONDS = Histogram(
    "server_stop_duration_seconds", "Time taken to stop the user server", ["status"]
)

prometheus_metrics_aliases = {
    "server-start": SERVER_START_DURATION_SECONDS,
    "kernel-start": KERNEL_START_DURATION_SECONDS,
    "code-execute": CODE_EXECUTE_DURATION_SECONDS,
    "kernel-stop": KERNEL_STOP_DURATION_SECONDS,
    "server-stop": SERVER_STOP_DURATION_SECONDS,
}


class ActionStatus(Enum):
    """
    Possible values for 'status' label of the metrics
    """

    success = "Success"
    failure = "Failure"

    def __str__(self):
        return self.value


for alias, metric in prometheus_metrics_aliases.items():
    for s in ActionStatus:
        metric.labels(status=s)


def get_user_token(username):
    api_token = os.environ["JUPYTERHUB_API_TOKEN"]
    api_url = os.environ["JUPYTERHUB_API_URL"]

    # Request a token for the user
    # Serice needs to have admin rights
    token_request_url = url_path_join(api_url, f"/users/{username}/tokens")
    resp = requests.post(
        token_request_url, headers={"Authorization": f"token {api_token}"}
    )
    return resp.json()["token"]


class HubMetricsHandler(HubAuthenticated, RequestHandler):
    def initialize(self, args, registry=REGISTRY):
        self.args = args
        self.registry = registry

    @authenticated
    async def get(self):
        user_token = get_user_token(self.args.username)

        text_stream = io.StringIO()
        with redirect_stdout(text_stream):
            hubtraf_check_status = await check_user(
                self.args.hub_url, self.args.username, user_token, json=True
            )

        if hubtraf_check_status == "completed":
            CHECK_COMPLETED.set(1)

        hubtraf_output = text_stream.getvalue()

        # Collect metrics from hubtraf
        for line in hubtraf_output.splitlines():
            hubtraf_metric = json.loads(line)
            status = hubtraf_metric["status"]
            if status in ["Success", "Failure"]:
                prometheus_metrics_aliases[hubtraf_metric["action"]].labels(
                    status=status
                ).observe(float(hubtraf_metric["duration"]))

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
