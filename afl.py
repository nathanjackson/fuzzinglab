import math
import random
import time


class BitFlipMutator:
    def __init__(self, n):
        self.n = n

    def __call__(self, test):
        # determine how many bytes we'll need to mutate
        n_bytes = (8 * math.ceil(self.n / 8.)) // 8
        # pick a random index
        byte_index = random.randrange(len(test) - n_bytes + 1)
        # get value
        value = int.from_bytes(test[byte_index:byte_index + n_bytes], signed=False, byteorder="little")
        # pick a random shift
        shift = random.randrange((n_bytes * 8) - self.n + 1)
        # compute mask
        mask = max(1, (2 ** self.n - 1)) << shift
        # update value
        value ^= mask
        # back to bytes
        new_bytes = value.to_bytes(length=n_bytes, byteorder="little", signed=False)
        # assign
        test[byte_index:byte_index + n_bytes] = new_bytes


class AddMutator:
    def __init__(self, min, max):
        self.min = min
        self.max = max

    def __call__(self, test):
        delta = random.randint(self.min, self.max)
        index = random.randrange(len(test))
        test[index] = (test[index] + delta) % 255


class HavocMutator:
    def __init__(self):
        self._mutators = [
            BitFlipMutator(1),
            BitFlipMutator(2),
            BitFlipMutator(3),
            BitFlipMutator(8),
            BitFlipMutator(16),
            BitFlipMutator(24),
            BitFlipMutator(32),
            AddMutator(-35, 35)
        ]

    def __call__(self, test):
        n = random.randint(1, 16)
        for i in range(n):
            mutator = random.choice(self._mutators)
            mutator(test)

class AflFuzzer:
    def __init__(self, target, corpus):
        self.target = target
        self.current_testcase_index = 0
        self.current_testcase_n_tests = 0
        self.corpus = []
        self.corpus_ns = []

        self.total_coverage = set()

        self._new_testcases = corpus.copy()

        self._execs = 0
        self._crashes = []
        self._cycles = 0

        self.havoc_mutator = HavocMutator()


    def step(self):
        self._execs += 1

        if self._new_testcases:
            testcase = self._new_testcases[0]
            start_ns = time.monotonic_ns()
            test_result = self.target(testcase)
            end_ns = time.monotonic_ns()
            assert 128 > test_result.exit_code
            delta_ns = end_ns - start_ns
            self.total_coverage.update(test_result.coverage)
            self._new_testcases = self._new_testcases[1:]
            self.corpus.append(testcase)
            self.corpus_ns.append(delta_ns)

            if 0 == self.current_testcase_n_tests:
                testcase_ns = self.corpus_ns[self.current_testcase_index]
                self.current_testcase_n_tests = 1024

        else:
            # get current testcase
            testcase = self.corpus[self.current_testcase_index]

            # create a new test from the current testcase
            test = bytearray(testcase)
            self.havoc_mutator(test)

            # measure
            test_result = self.target(test)
            if test_result.exit_code > 128:
                self._crashes += 1
            else:
                if not test_result.coverage.issubset(self.total_coverage):
                    # found a potential new testcase, add it to the new testcases list for calibration
                    self._new_testcases.append(bytes(test_result.test))


            self.current_testcase_n_tests -= 1
            if 0 == self.current_testcase_n_tests:
                self.current_testcase_index += 1
                if self.current_testcase_index == len(self.corpus):
                    self._cycles += 1
                    self.current_testcase_index = 0
                testcase_ns = self.corpus_ns[self.current_testcase_index]
                self.current_testcase_n_tests = 1024

        if self._execs > 0 and 0 == self._execs % 100:
            print("execs=%d testcases=%d crashes=%d cycles=%d tests=%d" % (self._execs, len(self.corpus), len(self._crashes), self._cycles, self.current_testcase_n_tests))
            print("testcase=%s" % (self.corpus[self.current_testcase_index]))

