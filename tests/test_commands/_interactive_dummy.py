#!/usr/bin/env python3
from __future__ import annotations

import time


class InteractiveDummyCommand:
    PROMPT = "(dummy) "

    def start(self):
        print("Started interactive dummy command")

    def send(self, input: str):
        print(f"Received input: {input}")
        time.sleep(0.5)

    def stop(self):
        print("Stopped interactive dummy command")

    def __call__(self):
        self.start()
        while True:
            input = input(self.PROMPT)
            cmd, _, args = input.partition(" ")
            if cmd == "stop":
                self.stop()
                break
            if cmd == "send":
                self.send(args)
            else:
                print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    InteractiveDummyCommand()()
