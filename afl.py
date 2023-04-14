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
        byte_index = random.randrange(max(1, len(test) - n_bytes + 1))
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
    def __init__(self, field_size, byteorder, min, max):
        self.field_size = field_size
        self.byteorder = byteorder
        self.min = min
        self.max = max

    def __call__(self, test):
        delta = random.randint(self.min, self.max)
        index = random.randrange(len(test))

        bytes_len = self.field_size // 8
        value = int.from_bytes(test[index:index+bytes_len], signed=False, byteorder=self.byteorder)

        value = (value + delta) % (2 ** self.field_size - 1)
        new_bytes = value.to_bytes(bytes_len, signed=False, byteorder=self.byteorder)

        test[index:index+bytes_len] = new_bytes

class InsertMutator:
    def __call__(self, test: bytearray):
        size = random.randrange(max(len(test) // 4, 1))
        fixed = random.choice([True, False])
        if fixed:
            b = random.randint(0, 255)
            bs = bytes([b] * size)
        else:
            bs = random.randbytes(size)
        index = random.randrange(len(test))
        for b in bs:
            test.insert(index, b)
            index = min(index + 1, len(bs) - 1)

class DeleteMutator:
    def __call__(self, test: bytearray):
        index = random.randrange(len(test))
        size = random.randrange( max(1, (len(test) - index) // 2))
        new = test[:index+1] + test[index+size-1:]
        if len(new) > 0:
            test.clear()
            test += new

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
            AddMutator(8, "little", -35, 35),
            AddMutator(16, "little", -35, 35),
            AddMutator(24, "little", -35, 35),
            AddMutator(32, "little", -35, 35),
            AddMutator(8, "big", -35, 35),
            AddMutator(16, "big", -35, 35),
            AddMutator(24, "big", -35, 35),
            AddMutator(32, "big", -35, 35),
        ]
        self._mutators = self._mutators * 4
        self._mutators.append(InsertMutator())
        self._mutators.append(DeleteMutator())

    def __call__(self, test):
        n = 1 << 1 + random.randint(0, 7)
        for i in range(n):
            mutator = random.choice(self._mutators)
            mutator(test)

class QueueEntry:
    def __init__(self, testcase, exec_us, cov_set, handicap, parent):
        self.testcase = testcase
        self.exec_us = exec_us
        self.cov_set = cov_set
        self.handicap = handicap
        self.parent = parent


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

        self._bitmap_hist = {}


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

        cqe = qe
        depth = 0
        while cqe != None:
            cqe = cqe.parent
            depth += 1

        if 0 <= depth <= 3:
            pass
        elif 4 <= depth <= 7:
            score *= 2
        elif 8 <= depth <= 13:
            score *= 3
        elif 14 <= depth <= 25:
            score *= 4
        else:
            score *= 5

        hits_scaled = math.log2(self._bitmap_hist[hash(frozenset(qe.cov_set))])

        factor = 1.0
        if 0 <= hits_scaled <= 1:
            factor = 4.0
        elif 2 <= hits_scaled <= 3:
            factor = 3.0
        elif 4 == hits_scaled:
            factor = 2.0

        score *= (min(32., factor) / 1.)

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
        return max(n, 16)

    def step(self):
        self._execs += 1

        if self._new_testcases:
            self._total_cal_execs += 1

            if isinstance(self._new_testcases[0], QueueEntry):
                qe = self._new_testcases[0]
                testcase = qe.testcase
            else:
                testcase = self._new_testcases[0]
                qe = None
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

            cov_hash = hash(frozenset(test_result.coverage))
            if cov_hash not in self._bitmap_hist:
                self._bitmap_hist[cov_hash] = 0
            self._bitmap_hist[cov_hash] += 1
            self.total_coverage.update(test_result.coverage)
            self._new_testcases = self._new_testcases[1:]

            if qe:
                parent = qe.parent
            else:
                parent = None

            qe = QueueEntry(testcase, delta_us, test_result.coverage, self._cycles - 1, parent)
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
            cov_hash = hash(frozenset(test_result.coverage))
            if cov_hash not in self._bitmap_hist:
                self._bitmap_hist[cov_hash] = 0
            self._bitmap_hist[cov_hash] += 1
            if test_result.exit_code > 128:
                self._crashes.append(test_result)
            else:
                if not test_result.coverage.issubset(self.total_coverage):
                    # found a potential new testcase, add it to the new testcases list for calibration
                    qe = QueueEntry(bytes(test_result.test), delta_us, test_result.coverage, self._cycles - 1, qe)
                    self._new_testcases.append(qe)
                    #self._new_testcases.append(bytes(test_result.test))


            self.current_testcase_n_tests -= 1
            if 0 == self.current_testcase_n_tests:
                self.current_testcase_index += 1
                if self.current_testcase_index == len(self.corpus):
                    self._cycles += 1
                    self.current_testcase_index = 0
                testcase_ns = self.corpus_ns[self.current_testcase_index]
                self.current_testcase_n_tests = self._calc_havoc_tests(self.current_testcase_index)

        assert self.current_testcase_n_tests >= 0
        if self._execs > 0 and 0 == self._execs % 10:
            print("execs=%d testcases=%d crashes=%d cycles=%d tests=%d" % (self._execs, len(self.corpus), len(self._crashes), self._cycles, self.current_testcase_n_tests))
            qe = self.corpus[self.current_testcase_index]
            cqe = qe
            depth = 0
            while cqe:
                cqe = cqe.parent
                depth += 1
            print("testcase=%s depth=%d" % (qe.testcase, depth))
            print(self._bitmap_hist)

