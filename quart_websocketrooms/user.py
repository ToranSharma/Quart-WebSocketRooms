import asyncio

class User():
    def __init__(self):
        self.room = None
        self.username = None
        self.host = False
        self.queue = asyncio.Queue()
