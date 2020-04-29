from setuptools import setup, find_packages

setup(
    name='fakecam',
    version='1.0.0',
    url='https://elder.dev/posts/open-source-virtual-background/',
    author='Daniel Llewellyn',
    author_email='diddledan@ubuntu.com',
    description='Fakecam',
    packages=find_packages(),    
    install_requires=[
        "numpy==1.18.2",
        "opencv-python==4.2.0.32",
        "requests==2.23.0",
        "pyfakewebcam==0.1.0",
        "pycairo==1.19.1",
        "PyGObject==3.36.0",
    ],
    entry_points={
        'console_scripts':[
            'fakecamcli=fakecam.main:main',
            'fakecamgui=fakecam.gui:main',
        ],
    },
)
