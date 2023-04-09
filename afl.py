import random
import time

import bitstring


class BitFlipMutator:
    def __init__(self, n):
        self.n = n

    def __call__(self, test):
        # pick a random byte
        byte_index = random.randrange(len(test))
        # pick a random offset within the byte
        shift = random.randrange(8 - self.n)
        # compute mask
        mask = max(1, (self.n ** 2 - 1)) << shift
        test[byte_index] ^= mask

class AflFuzzer:
    def __init__(self, target, corpus):
        self.target = target
        self.current_testcase_index = 0
        self.corpus = []
        self.corpus_ns = []

        self.total_coverage = set()

        self._new_testcases = corpus.copy()

        self._execs = 0
        self._crashes = []

    def step(self):
        self._execs += 1

        if self._new_testcases:
            testcase = self._new_testcases[0]
            start_ns = time.monotonic_ns()
            test_result = self.target(testcase)
            end_ns = time.monotonic_ns()
            assert 0 == test_result.exit_code
            delta_ns = end_ns - start_ns
            self.total_coverage.update(test_result.coverage)
            self._new_testcases = self._new_testcases[1:]
            self.corpus.append(testcase)
            self.corpus_ns.append(delta_ns)
        else:
            testcase = self.corpus[self.current_testcase_index]
            testcase_ns = self.corpus_ns[self.current_testcase_index]

            test = bytearray(testcase)
            BitFlipMutator(1)(test)
            print(test)

            raise NotImplementedError("Not yet implemented")

        if self._execs > 0 and 0 == self._execs % 10:
            print("execs=%d testcases=%d crashes=%d" % (self._execs, len(self.corpus), len(self._crashes)))

