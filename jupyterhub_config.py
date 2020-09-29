c.JupyterHub.authenticator_class = "dummy"
c.JupyterHub.spawner_class = "simple"

c.Authenticator.admin_users = {"hubtraf"}
c.JupyterHub.services = [
    {
        "name": "monitor-hub",
        "admin": True,
        "url": "http://127.0.0.1:10101",
        "command": ["monitor-hub", "http://127.0.0.1:8000", "hubtraf"],
    }
]
