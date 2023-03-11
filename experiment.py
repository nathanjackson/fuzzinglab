import sys

import dumb
import simple_guided
import qlearning

import matplotlib.pyplot as plt


def fuzzme(test):
    if 3 > len(test):
        return
    if test[0] == b'b'[0]:
        if test[1] == b'u'[0]:
            if test[2] == b'g'[0]:
                assert False


def instrumented_fuzzme(tracker, test):
    if 3 > len(test):
        tracker.add_coverage()
        return
    if test[0] == b'b'[0]:
        tracker.add_coverage()
        if test[1] == b'u'[0]:
            tracker.add_coverage()
            if test[2] == b'g'[0]:
                tracker.add_coverage()
                assert False
    tracker.add_coverage()


class CoverageTracker:
    def __init__(self, fn):
        self.fn = fn
        self.lifetime_coverage = set()
        self.last_coverage = set()

    def add_coverage(self):
        location = sys._getframe().f_back.f_lineno
        self.last_coverage.add(location)

    def __call__(self, test):
        self.last_coverage.clear()
        self.fn(self, test)
        self.lifetime_coverage.update(self.last_coverage)


if __name__ == "__main__":
    tracker = CoverageTracker(instrumented_fuzzme)
    dumb_fuzzer = dumb.DumbFuzzer(tracker)

    dumb_fuzzer_cov = []

    while 0 == dumb_fuzzer.crashes:
        dumb_fuzzer.step()
        dumb_fuzzer_cov.append(len(tracker.lifetime_coverage))

    print("Dumb Fuzzer Execs to Crash: %d" % (dumb_fuzzer.execs, ))

    tracker.lifetime_coverage.clear()
    tracker.last_coverage.clear()

    simple_guided_fuzzer = simple_guided.SimpleCoverageGuidedFuzzer(tracker)
    simple_guided_cov = []

    while 0 == simple_guided_fuzzer.crashes:
        simple_guided_fuzzer.step()
        simple_guided_cov.append(len(tracker.lifetime_coverage))

    print("Simple Covergae Guided Fuzzer Execs to Crash: %d" % (simple_guided_fuzzer.execs,))

    tracker.lifetime_coverage.clear()
    tracker.last_coverage.clear()

    qlearning_fuzzer = qlearning.QLearningGuidedFuzzer(tracker)
    qlearning_cov = []

    while 0 == qlearning_fuzzer.crashes:
        qlearning_fuzzer.step()
        qlearning_cov.append(len(tracker.lifetime_coverage))

    print("Q-Learning Fuzzer Execs to Crash: %d" %(qlearning_fuzzer.iterations,))

    x = [i for i in range(dumb_fuzzer.execs)]
    plt.plot(x, dumb_fuzzer_cov, c='blue')

    x = [i for i in range(simple_guided_fuzzer.execs)]
    plt.plot(x, simple_guided_cov, c='green')

    x = [i for i in range(qlearning_fuzzer.iterations)]
    plt.plot(x, qlearning_cov, c='red')

    plt.show()
