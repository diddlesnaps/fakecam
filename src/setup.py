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
        "frozen_graph.pb",
        "LICENSE",
    ]},
    install_requires=[
        "numpy==1.19.5",
        # "opencv-python==4.2.0.32",
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
