import random

class DumbFuzzer:
    def __init__(self, fn):
        self.fn = fn
        self.execs = 0
        self.crashes = 0

    def step(self):
        self.execs += 1
        test_length = random.randint(1, 10)
        test = random.randbytes(test_length)

        if self.fn(test):
            self.crashes += 1
