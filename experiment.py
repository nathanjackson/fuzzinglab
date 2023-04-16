#!/usr/bin/env python
import os
#import sys

import dumb
import simple_guided
#import qlearning
import qemu_afl
import afl

#import matplotlib.pyplot as plt



def main():
    #os.sched_setaffinity(0, {0})

    fuzzme = qemu_afl.AflForkServerTarget("./qemu/build/qemu-x86_64 -E LD_BIND_NOW=1 ./fuzzme /tmp/payload")
    #fuzzme = qemu_afl.AflForkServerTarget("./qemu/build/qemu-x86_64 -cpu max -E LD_BIND_NOW=1 /home/nathan/src/buffer-overflow-dataset/dataset/imgdataopt /tmp/payload /dev/null")
    
    fuzzer = afl.AflFuzzer(fuzzme, [b"AAAAAAAAAAAAAAAA"])
    #fuzzer = afl.AflFuzzer(fuzzme, [b'\x00asm\x00\x00\x00\x00', b'\x00\x00\x00\x00\x00\x00\x00\x00'])

    while not fuzzer.memento.crashes:
        fuzzer.step()

    print(fuzzer.memento.crashes)

#    dumb_fuzzer = dumb.DumbFuzzer(fuzzme)
#    while 0 == dumb_fuzzer.crashes:
#        if 0 < dumb_fuzzer.execs and 0 == dumb_fuzzer.execs % 10:
#            print(f"execs={dumb_fuzzer.execs}")
#        dumb_fuzzer.step()

#    simple_guided_fuzzer = simple_guided.SimpleCoverageGuidedFuzzer(fuzzme)

#    while 0 == simple_guided_fuzzer.crashes:
#        if 0 < simple_guided_fuzzer.execs and 0 == simple_guided_fuzzer.execs % 10:
#            print(f"execs={simple_guided_fuzzer.execs}, cs={len(simple_guided_fuzzer.test_suite)}")
#        simple_guided_fuzzer.step()

#    print("Simple Covergae Guided Fuzzer Execs to Crash: %d" % (simple_guided_fuzzer.execs,))
#
#    tracker.lifetime_coverage.clear()
#    tracker.last_coverage.clear()
#
#    qlearning_fuzzer = qlearning.QLearningGuidedFuzzer(tracker)
#    qlearning_cov = []
#
#    while 0 == qlearning_fuzzer.crashes:
#        qlearning_fuzzer.step()
#        qlearning_cov.append(len(tracker.lifetime_coverage))
#
#    print("Q-Learning Fuzzer Execs to Crash: %d" %(qlearning_fuzzer.iterations,))
#
#    x = [i for i in range(dumb_fuzzer.execs)]
#    plt.plot(x, dumb_fuzzer_cov, c='blue')
#
    #x = [i for i in range(simple_guided_fuzzer.execs)]
    #plt.plot(x, simple_guided_cov, c='green')
#
#    x = [i for i in range(qlearning_fuzzer.iterations)]
#    plt.plot(x, qlearning_cov, c='red')
#
    #plt.show()

if __name__ == "__main__":
    main()