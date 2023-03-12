import random


class SimpleCoverageGuidedFuzzer:
    def __init__(self, tracker):
        self.execs = 0
        self.crashes = 0
        self.tracker = tracker
        self.test_suite = []

    def make_test(self):
        if 0 == len(self.test_suite):
            length = random.randrange(1, 10)
            return random.randbytes(length)

        testcase = random.choice(list(self.test_suite))

        # replace a single byte
        test = bytearray(testcase)
        index = random.randrange(len(testcase))
        test[index] = random.randrange(256)

        # append some random data
        append_len = random.randrange(5)
        test += random.randbytes(append_len)

        return bytes(test)


    def step(self):
        self.execs += 1

        test = self.make_test()

        before_cov = self.tracker.lifetime_coverage.copy()
        if self.tracker(test):
            self.crashes += 1
        after_cov = self.tracker.lifetime_coverage.copy()

        if 0 < len(after_cov - before_cov):
            self.test_suite.append(test)
