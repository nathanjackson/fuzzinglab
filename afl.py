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
        n = 1 << 1 + random.randint(0, 7)
        for i in range(n):
            mutator = random.choice(self._mutators)
            mutator(test)

class QueueEntry:
    def __init__(self, testcase, exec_us, cov_set, handicap):
        self.testcase = testcase
        self.exec_us = exec_us
        self.cov_set = cov_set
        self.handicap = handicap


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

        self._total_us = 0

        self._total_cal_us = 0
        self._total_cal_execs = 0


    def _compute_score(self, index):
        avg_exec_us = self._total_cal_us / self._total_cal_execs
        avg_cov = len(self.total_coverage) / len(self.corpus)
        exec_us = self.corpus_ns[index] // 1000

        qe = self.corpus[index]
        score = 100

        if exec_us * 0.1 > avg_exec_us:
            score = 10
        elif exec_us * 0.25 > avg_exec_us:
            score = 25
        elif exec_us * 0.5 > avg_exec_us:
            score = 50
        elif exec_us * 0.75 > avg_exec_us:
            score = 75
        elif exec_us * 4 < avg_exec_us:
            score = 300
        elif exec_us * 3 < avg_exec_us:
            score = 200
        elif exec_us * 2 < avg_exec_us:
            score = 150

        if len(qe.cov_set) * 0.3 > avg_cov:
            score *= 3
        elif len(qe.cov_set) * 0.5 > avg_cov:
            score *= 2
        elif len(qe.cov_set) * 0.75 > avg_cov:
            score *= 1.5
        elif len(qe.cov_set) * 3 < avg_cov:
            score *= 0.25
        elif len(qe.cov_set) * 2 < avg_cov:
            score *= 0.5
        elif len(qe.cov_set) * 1.5 < avg_cov:
            score *= 0.75

        if qe.handicap >= 4:
            score *= 4
            qe.handicap -= 4
        elif qe.handicap > 0:
            score *= 2
            qe.handicap -= 1

        print("score=", score)
        return score

    def _calc_havoc_tests(self, index):
        avg_us = self._total_us / self._execs
        print("avg_us=", avg_us)
        havoc_div = 1
        if avg_us > 50000:
            havoc_div = 10
        elif avg_us > 20000:
            havoc_div = 5
        elif avg_us > 10000:
            havoc_div = 2
        score = self._compute_score(index)
        n = 256 * (score // havoc_div // 100)
        return n

    def step(self):
        self._execs += 1

        if self._new_testcases:
            self._total_cal_execs += 1

            testcase = self._new_testcases[0]
            start_ns = time.monotonic_ns()
            test_result = self.target(testcase)
            end_ns = time.monotonic_ns()
            assert 128 > test_result.exit_code

            # on the first exec, run twice to avoid JIT warmup penalty
            if 1 == self._execs:
                start_ns = time.monotonic_ns()
                test_result = self.target(testcase)
                end_ns = time.monotonic_ns()
                assert 128 > test_result.exit_code

            delta_ns = end_ns - start_ns
            delta_us = (delta_ns // 1000)
            self._total_cal_us += delta_us
            self._total_us += delta_us

            self.total_coverage.update(test_result.coverage)
            self._new_testcases = self._new_testcases[1:]

            qe = QueueEntry(testcase, delta_us, test_result.coverage, self._cycles - 1)
            self.corpus.append(qe)
            self.corpus_ns.append(delta_ns)

            if 0 == self.current_testcase_n_tests:
                testcase_ns = self.corpus_ns[self.current_testcase_index]
                self.current_testcase_n_tests = self._calc_havoc_tests(self.current_testcase_index)

        else:
            # get current testcase
            qe = self.corpus[self.current_testcase_index]

            # create a new test from the current testcase
            test = bytearray(qe.testcase)
            self.havoc_mutator(test)

            # measure
            start_ns = time.monotonic_ns()
            test_result = self.target(test)
            end_ns = time.monotonic_ns()
            delta_us = (end_ns - start_ns) // 1000
            self._total_us += delta_us
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
                self.current_testcase_n_tests = self._calc_havoc_tests(self.current_testcase_index)

        if self._execs > 0 and 0 == self._execs % 10:
            print("execs=%d testcases=%d crashes=%d cycles=%d tests=%d" % (self._execs, len(self.corpus), len(self._crashes), self._cycles, self.current_testcase_n_tests))
            print("testcase=%s" % (self.corpus[self.current_testcase_index].testcase))

