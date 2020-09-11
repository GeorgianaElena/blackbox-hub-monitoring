import os
import sys

c.JupyterHub.services = [
    {
        'name': 'monitor-hub',
        'url': 'http://127.0.0.1:10101',
        'command': ['monitor-hub', 'http://127.0.0.1:8000'],
    },
]