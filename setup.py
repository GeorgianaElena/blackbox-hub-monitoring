from setuptools import find_packages, setup

setup(
    name="hub_metrics_collector",
    version="0.1",
    description="Blackbox monitoring app for JupyterHubs",
    author="Project Jupyter Contributors",
    author_email="jupyter@googlegroups.com",
    packages=find_packages(),
    platforms="any",
    install_requires=[
        "prometheus_client",
        "hubtraf @ git+https://github.com/yuvipanda/hubtraf.git#egg=hubtraf",
        "asyncio",
    ],
    entry_points={
        "console_scripts": ["monitor-hub = hub_metrics_collector.monitor:main"]
    },
)
