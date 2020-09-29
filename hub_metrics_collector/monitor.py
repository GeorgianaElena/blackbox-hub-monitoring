import argparse
import os
import subprocess
from urllib.parse import urlparse

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
    "server_start_duration_seconds", "Time taken to start the user server"
)
KERNEL_START_DURATION_SECONDS = Histogram(
    "kernel_start_duration_seconds", "Time taken to start the user server"
)
CODE_EXECUTE_DURATION_SECONDS = Histogram(
    "code_execute_duration_seconds", "Time taken to start the user server"
)
KERNEL_STOP_DURATION_SECONDS = Histogram(
    "kernel_stop_duration_seconds", "Time taken to start the user server"
)
SERVER_STOP_DURATION_SECONDS = Histogram(
    "server_stop_duration_seconds", "Time taken to start the user server"
)

prometheus_metrics_aliases = {
    "server-start": SERVER_START_DURATION_SECONDS,
    "kernel-start": KERNEL_START_DURATION_SECONDS,
    "code-execute": CODE_EXECUTE_DURATION_SECONDS,
    "kernel-stop": KERNEL_STOP_DURATION_SECONDS,
    "server-stop": SERVER_STOP_DURATION_SECONDS,
}


def parse_hubtraf_metrics(hubtraf_metics):
    metrics = {}
    for line in hubtraf_metics.splitlines():
        if line.startswith("Success:"):
            # words list example:
            # ['Success:', 'server-start', 'hubtraf', 'duration:2.417068515002029']
            words = line.split()
            metric_name = words[1]
            metric_duration = words[3].split(":")[1]
            metrics[metric_name] = metric_duration
    return metrics


class HubMetricsHandler(HubAuthenticated, RequestHandler):
    def initialize(self, args, registry=REGISTRY):
        self.args = args
        self.registry = registry

    @authenticated
    async def get(self):
        args = self.args

        out = subprocess.check_output(["hubtraf-check", args.hub_url, args.username])

        hubtraf_metics_s = json.dumps(out.decode("utf-8"))
        hubtraf_metics = json.loads(hubtraf_metics_s)

        """
        hubtraf-check has 6 phases and 5 of them return a "Success" message
        when they complete successfully. These are:
        - server-start
        - kernel-start
        - kernel-connect (this returns a debug "phase:complete" when done)
        - code-execute
        - kernel-stop
        - server-stop
        """
        if hubtraf_metics.count("Success") == 5:
            CHECK_COMPLETED.set(1)

        metrics = parse_hubtraf_metrics(hubtraf_metics)

        # Collect metrics from hubtraf
        for metric, duration in metrics.items():
            prometheus_metrics_aliases[metric].observe(float(duration))

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
    # Serice needs to have admin rights
    token_request_url = url_path_join(api_url, f"/users/{args.username}/tokens")
    resp = requests.post(
        token_request_url, headers={"Authorization": f"token {api_token}"}
    )
    user_token = resp.json()["token"]
    # hubtraf uses this env var for authorization, so we  need to make it be
    # the user token
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
