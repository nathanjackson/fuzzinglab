import random

import numpy as np


class AdvanceTestcaseAction:
    def __init__(self, test_suite, delta):
        self.test_suite = test_suite
        self.delta = delta

    def do(self, current_index):
        return (current_index + self.delta) % (len(self.test_suite))


class QLearningGuidedFuzzer:
    START = 0
    ON_PATH = 1
    OFF_PATH = 2
    CRASHED = 3

    VALID_STATES = set([START, ON_PATH, OFF_PATH, CRASHED])

    def __init__(self, tracker):
        self.iterations = 0
        self.crashes = 0
        self.tracker = tracker
        self.test_suite = []
        self.current_testcase_index = None

        self.action_space = [
            AdvanceTestcaseAction(self.test_suite, 0),  # don't change test case
            AdvanceTestcaseAction(self.test_suite, 1),  # next test case
            AdvanceTestcaseAction(self.test_suite, -1),  # prev test case
        ]
        self.state = self.START

        self.q_table = np.zeros((len(self.VALID_STATES), len(self.action_space)))

        self.eps = 1.0
        self.eps_decay = 0.05
        self.eps_min = 0.01
        self.a = 0.1
        self.g = 0.1

        self._largest_cov = 0
        self._update_eps = False

    def _calibrate(self):
        t_len = random.randint(1, 10)
        t = random.randbytes(t_len)
        self.test_suite.append(t)

        self.tracker(t)
        self._largest_cov = len(self.tracker.lifetime_coverage)
        self.current_testcase_index = 0

    def _make_test(self):
        testcase = self.test_suite[self.current_testcase_index]

        # replace a single byte
        test = bytearray(testcase)
        index = random.randrange(len(testcase))
        test[index] = random.randrange(256)

        # append some random data
        append_len = random.randrange(5)
        test += random.randbytes(append_len)

        return test

    def step(self):
        self.iterations += 1

        if 0 == len(self.test_suite):
            self._calibrate()
            return

        if random.random() < self.eps:
            # Explore
            action_index = random.randrange(len(self.action_space))
        else:
            # Exploit
            action_index = np.argmax(self.q_table[self.state, :])

        # Adjust current test case and generate a new test.
        action = self.action_space[action_index]
        self.current_testcase_index = action.do(self.current_testcase_index)
        test = self._make_test()

        # Measure the reward (exec)
        prev_global = self.tracker.lifetime_coverage.copy()
        try:
            self.tracker(test)
        except AssertionError:
            new_state = self.CRASHED
            self.crashes += 1
        new_cov = len(self.tracker.last_coverage - prev_global)
        reward = 0
        if len(self.tracker.last_coverage) >= self._largest_cov:
            new_state = self.ON_PATH
            if new_cov > 0:
                self._update_eps = True
                self.test_suite.append(test)
                reward += 1
        else:
            reward -= 1
            new_state = self.OFF_PATH

        # Update Q Table
        self.q_table[self.state, action_index] = (1 - self.a) * self.q_table[self.state, action_index] + self.a * (reward + self.g * np.max(self.q_table[new_state:]))

        self.state = new_state

        if self._update_eps:
            self.eps = max(self.eps - self.eps_decay, self.eps_min)

        self._largest_cov = max(len(self.tracker.last_coverage), self._largest_cov)
