import random

class DumbFuzzer:
    def __init__(self, target):
        self.target = target
        self.execs = 0
        self.crashes = 0

    def step(self):
        self.execs += 1
        test_length = random.randint(1, 100)
        test = random.randbytes(test_length)

        test_result = self.target(test)

        if test_result.exit_code > 128:
            self.crashes += 1
