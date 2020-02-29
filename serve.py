#!/usr/bin/env python

from src.bot import *
from src.config.config import *

if __name__ == '__main__':
    bot = Main(config).run()
