# Blackbox monitoring app for JupyterHubs

Whenever a hub goes down, we should try and make sure that it is robots who tell us, not humans.
Blackbox monitoring app tests how well things perform from a user perspective.

Uses [hubtraf](https://github.com/yuvipanda/hubtraf) to simulate a hub user and exposes
[Prometheus](https://prometheus.io/) metrics about user activity.
