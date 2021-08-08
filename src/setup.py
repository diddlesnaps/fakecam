from setuptools import setup, find_packages

from fakecam.about import name, version, description, project_url, author, author_email
setup(
    name=name,
    version=version,
    description=description,
    url=project_url,
    author=author,
    author_email=author_email,
    packages=find_packages(),
    package_dir={"fakecam": "fakecam"},
    package_data={"fakecam": [
        "ui/fakecam.glade",
        "ui/hologram.png",
        "LICENSE",

        # mobileNet
        "mobileNet/8/050/1/frozen_graph.pb",
        "mobileNet/8/050/2/frozen_graph.pb",
        "mobileNet/8/050/4/frozen_graph.pb",

        "mobileNet/8/075/1/frozen_graph.pb",
        "mobileNet/8/075/2/frozen_graph.pb",
        "mobileNet/8/075/4/frozen_graph.pb",

        "mobileNet/8/100/1/frozen_graph.pb",
        "mobileNet/8/100/2/frozen_graph.pb",
        "mobileNet/8/100/4/frozen_graph.pb",

        "mobileNet/16/050/1/frozen_graph.pb",
        "mobileNet/16/050/2/frozen_graph.pb",
        "mobileNet/16/050/4/frozen_graph.pb",

        "mobileNet/16/075/1/frozen_graph.pb",
        "mobileNet/16/075/2/frozen_graph.pb",
        "mobileNet/16/075/4/frozen_graph.pb",

        "mobileNet/16/100/1/frozen_graph.pb",
        "mobileNet/16/100/2/frozen_graph.pb",
        "mobileNet/16/100/4/frozen_graph.pb",

        # resNet
        "resNet/16/100/1/frozen_graph.pb",
        "resNet/16/100/2/frozen_graph.pb",
        "resNet/16/100/4/frozen_graph.pb",

        "resNet/32/100/1/frozen_graph.pb",
        "resNet/32/100/2/frozen_graph.pb",
        "resNet/32/100/4/frozen_graph.pb",
    ]},
    install_requires=[
        "numpy==1.19.5",
        "requests==2.25.1",
        "pyfakewebcam==0.1.0",
        "pycairo==1.20.0",
        "PyGObject==3.38.0",
        "typing_extensions==3.7.4.3",
    ],
    entry_points={
        'console_scripts': [
            'fakecamcli=fakecam.cli:main',
            'fakecamgui=fakecam.gui:main',
        ],
    },
)
