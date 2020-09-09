import argparse
import asyncio
from functools import partial
from hubtraf.user import User
from hubtraf.auth.dummy import login_dummy

from prometheus_client import make_wsgi_app, Gauge
from wsgiref.simple_server import make_server


SERVER_STARTED = Gauge("server_started", "whether or not the user's server started")

metrics_app = make_wsgi_app()


def get_args():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "hub_url", help="Hub URL to send traffic to (without a trailing /)"
    )
    argparser.add_argument("username", help="Name of user to check")
    args = argparser.parse_args()

    return args


async def monitor():
    # Default metric value
    SERVER_STARTED.set(False)

    args = get_args()

    # Simulate a hub user
    async with User(
        args.username, args.hub_url, partial(login_dummy, password="")
    ) as u:
        # Login user
        user_logged_in = await u.login()

        # Start user server
        server_started = await u.ensure_server_simulate()
        SERVER_STARTED.set(server_started)

        # Start kernel
        await u.start_kernel()

        # Verify computation works
        await u.assert_code_output("2 * 5", "10", 10)
        # todo: write something to home directory


def blackbox_hub_monitoring_app(environ, start_fn):

    if environ["PATH_INFO"] == "/metrics":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(monitor())
        return metrics_app(environ, start_fn)


def main():
    httpd = make_server("", 8888, blackbox_hub_monitoring_app)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
