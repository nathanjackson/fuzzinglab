import random


class SimpleCoverageGuidedFuzzer:
    def __init__(self, target):
        self.execs = 0
        self.crashes = 0
        self.target = target
        self.test_suite = []
        self._lifetime_coverage = set()

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
        #test = b"bug"

        test_result = self.target(test)

        if test_result.exit_code > 128:
            self.crashes += 1

        if not test_result.coverage.issubset(self._lifetime_coverage):
            self.test_suite.append(test_result.test)
            self._lifetime_coverage.update(test_result.coverage)
