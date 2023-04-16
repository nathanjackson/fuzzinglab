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

class CopyMutator:
    def __call__(self, test: bytearray):
        index = random.randrange(len(test))
        size = random.randrange( max(2, (len(test) - index) // 4 ))
        value = test[index]
        for b in [value for _ in range(size)]:
            test.insert(index, b)

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
        self._mutators.append(CopyMutator())

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


    def perf_score(self, memento):
        avg_exec_us = memento.total_calibration_time_us / memento.total_calibration_execs
        avg_cov = sum([len(x.cov_set) for x in memento.test_cases]) / len(memento.test_cases)

        score = 100

        exec_us = self.exec_us
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

        cov_set = self.cov_set
        if len(cov_set) * 0.3 > avg_cov:
            score *= 3
        elif len(cov_set) * 0.5 > avg_cov:
            score *= 2
        elif len(cov_set) * 0.75 > avg_cov:
            score *= 1.5
        elif len(cov_set) * 3 < avg_cov:
            score *= 0.25
        elif len(cov_set) * 2 < avg_cov:
            score *= 0.5
        elif len(cov_set) * 1.5 < avg_cov:
            score *= 0.75

        if self.handicap >= 4:
            score *= 4
            self.handicap -= 4
        elif self.handicap > 0:
            score *= 2
            self.handicap -= 1

        cqe = self
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

        hits_scaled = math.log2(memento.coverage_set_hits[hash(frozenset(cov_set))])

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


class AflMemento:
    def __init__(self):
        self.pending_tests = []
        self.test_cases = []

        # Coverage Tracking
        self.total_coverage = set()
        self.coverage_set_hits = dict()

        # Calibration data
        self.total_calibration_time_us = 0
        self.total_calibration_execs = 0

        # Havoc data
        self.cycle_iterator = None
        self.current_test_case = None
        self.remaining_test_count = 0

        # Overall Metrics
        self.total_us = 0
        self.total_execs = 0
        self.cycle_count = 0
        self.crashes = []


class CalibratingState:
    def __init__(self, afl_fuzzer):
        self._afl_fuzzer = afl_fuzzer
        assert len(self._afl_fuzzer.memento.pending_tests) > 0
        self._test_iterator = iter(self._afl_fuzzer.memento.pending_tests)
        self._current_test_parent, self._current_test = next(self._test_iterator)
        self._previous_cov = None

    def name(self):
        return "calibrating"

    def internal_step(self):
        test_result = self._afl_fuzzer.run_test(self._current_test)
        time_us = test_result.time_ns // 1000
        self._afl_fuzzer.memento.total_us += time_us
        self._afl_fuzzer.memento.total_execs += 1
        if not self._previous_cov:
            self._previous_cov = test_result.coverage
            return self

        assert self._previous_cov == test_result.coverage

        self._afl_fuzzer.memento.total_calibration_time_us += time_us
        self._afl_fuzzer.memento.total_calibration_execs += 1

        if not test_result.coverage.issubset(self._afl_fuzzer.memento.total_coverage):
            self._afl_fuzzer.memento.total_coverage.update(test_result.coverage)
            queue_entry = QueueEntry(self._current_test, time_us, test_result.coverage, self._afl_fuzzer.memento.cycle_count, self._current_test_parent)
            self._afl_fuzzer.memento.test_cases.append(queue_entry)

        cov_hash = hash(frozenset(test_result.coverage))
        if cov_hash not in self._afl_fuzzer.memento.coverage_set_hits:
            self._afl_fuzzer.memento.coverage_set_hits[cov_hash] = 0
        self._afl_fuzzer.memento.coverage_set_hits[cov_hash] += 1

        self._afl_fuzzer.memento.pending_tests.remove((self._current_test_parent, self._current_test))

        self._previous_cov = None
        try:
            self._current_test_parent, self._current_test = next(self._test_iterator)
        except StopIteration:
            return HavocState(self._afl_fuzzer)

        return self


class HavocState:
    def __init__(self, afl_fuzzer):
        self._afl_fuzzer = afl_fuzzer
        self._mutator = HavocMutator()

    def name(self):
        return "havoc"

    def _calc_test_count(self, test_case):
        avg_us = self._afl_fuzzer.memento.total_us / self._afl_fuzzer.memento.total_execs
        print("avg_us=", avg_us)
        havoc_div = 1
        if avg_us > 50000:
            havoc_div = 10
        elif avg_us > 20000:
            havoc_div = 5
        elif avg_us > 10000:
            havoc_div = 2
        perf_score = test_case.perf_score(self._afl_fuzzer.memento)
        n = 256 * (perf_score // havoc_div // 100)
        return max(int(n), 16)
    def internal_step(self):
        if not self._afl_fuzzer.memento.cycle_iterator:
            self._afl_fuzzer.memento.cycle_iterator = iter(self._afl_fuzzer.memento.test_cases)
            self._afl_fuzzer.memento.current_test_case = next(self._afl_fuzzer.memento.cycle_iterator)
            self._afl_fuzzer.memento.remaining_test_count = self._calc_test_count(self._afl_fuzzer.memento.current_test_case)
        elif 0 == self._afl_fuzzer.memento.remaining_test_count:
            try:
                self._afl_fuzzer.memento.current_test_case = next(self._afl_fuzzer.memento.cycle_iterator)
            except StopIteration:
                self._afl_fuzzer.memento.cycle_count += 1
                self._afl_fuzzer.memento.cycle_iterator = iter(self._afl_fuzzer.memento.test_cases)
                self._afl_fuzzer.memento.current_test_case = next(self._afl_fuzzer.memento.cycle_iterator)
            self._afl_fuzzer.memento.remaining_test_count = self._calc_test_count(self._afl_fuzzer.memento.current_test_case)


        test = bytearray(self._afl_fuzzer.memento.current_test_case.testcase)
        self._mutator(test)
        test_result = self._afl_fuzzer.run_test(test)

        self._afl_fuzzer.memento.total_execs += 1
        self._afl_fuzzer.memento.total_us += test_result.time_ns // 1000

        cov_hash = hash(frozenset(test_result.coverage))
        if cov_hash not in self._afl_fuzzer.memento.coverage_set_hits:
            self._afl_fuzzer.memento.coverage_set_hits[cov_hash] = 0
        self._afl_fuzzer.memento.coverage_set_hits[cov_hash] += 1

        if test_result.exit_code > 128:
            self._afl_fuzzer.memento.crashes.append(test)
        elif not test_result.coverage.issubset(self._afl_fuzzer.memento.total_coverage):
            self._afl_fuzzer.memento.pending_tests.append((self._afl_fuzzer.memento.current_test_case, test))

        self._afl_fuzzer.memento.remaining_test_count -= 1

        if 0 == self._afl_fuzzer.memento.remaining_test_count and 0 < len(self._afl_fuzzer.memento.pending_tests):
            return CalibratingState(self._afl_fuzzer)
        return self

class AflFuzzer:
    def __init__(self, target, starting_corpus):
        self.target = target
        self.memento = AflMemento()

        self.memento.pending_tests += [(None, x) for x in starting_corpus]

        self.state = CalibratingState(self)

    def run_test(self, test):
        return self.target(test)

    def step(self):
        if self.memento.total_execs > 0 and self.memento.total_execs % 10 == 0:
            print("state=%s testcases=%d crashes=%d pending=%d cycles=%d tests=%d" % (self.state.name(), len(self.memento.test_cases), len(self.memento.crashes), len(self.memento.pending_tests), self.memento.cycle_count, self.memento.remaining_test_count))
            print(self.memento.current_test_case.testcase)
            print(self.memento.coverage_set_hits)
        self.state = self.state.internal_step()

