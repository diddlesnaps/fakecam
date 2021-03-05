from os import path

name         = 'Fakecam'
version      = '3.0.0'
description  = 'Virtual Backgrounds for your video conferences and streaming presentations'
project_url  = 'https://github.com/diddlesnaps/fakecam/'
donate_url   = 'https://github.com/sponsors/diddledan/'
donate_label = 'Donate to support the project'
author       = 'Daniel Llewellyn'
author_email = 'diddledan@ubuntu.com'

authors      = [
    "Daniel Llewellyn",
    "Benjamin Elder",
    "Google, Inc.",
]

translators  = []

artists      = []

documentors  = []

copyright    = """
Copyright © 2020-2021 Daniel Llewellyn
Copyright © 2020 Benjamin Elder
Copyright © 2019 Google, Inc.
"""

license      = ''
with open(path.join(path.dirname(__file__), 'LICENSE'), 'r') as f:
    license = "".join(f.readlines())

if __name__ == "__main__":
    print(version)
