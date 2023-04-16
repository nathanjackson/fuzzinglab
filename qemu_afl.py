import os
import time

import sysv_ipc


class TestResult:
    def __init__(self, test, exit_code, coverage, time_ns):
        self.test = test
        self.exit_code = exit_code
        self.coverage = coverage
        self.time_ns = time_ns


def bitmap_to_set(m):
    res = set()
    bit = 0
    for byte in m:
        for i in range(8):
            if (byte >> i) & 0x1:
                res.add(bit)
            bit += 1
    return res


class AflForkServerTarget:
    def __init__(self, command, forksrv_fd=198):
        self.lifetime_coverage = set()
        self.last_coverage = set()

        map_size = 1 << 16
        self.shm = sysv_ipc.SharedMemory(sysv_ipc.IPC_PRIVATE, size=map_size)

        st_pipe = os.pipe()
        ctl_pipe = os.pipe()

        fsrv_pid = os.fork()
        if not fsrv_pid:
            # redir stdout and stderr to /dev/null
            devnull = os.open("/dev/null", os.O_WRONLY)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)

            # setup control and status pipes
            os.dup2(ctl_pipe[0], forksrv_fd)
            os.dup2(st_pipe[1], forksrv_fd + 1)

            # close original fds
            os.close(st_pipe[0])
            os.close(st_pipe[1])
            os.close(ctl_pipe[0])
            os.close(ctl_pipe[1])

            args = command.split()
            os.execve(args[0], args, {
                "__AFL_SHM_ID": str(self.shm.id),
                "LD_BIND_NOW": "1"
            })
            raise Exception("Exec Failed")
        os.close(ctl_pipe[0])
        os.close(st_pipe[1])

        self.fsrv_ctl_fd = ctl_pipe[1]
        self.fsrv_st_fd = st_pipe[0]

        # read handshake
        self._read_status_pipe()

    def __call__(self, test):
        with open("/tmp/payload", "wb") as f:
            f.write(test)

        self.shm.write(bytes([0 for _ in range(self.shm.size)]))

        start_ns = time.monotonic_ns()
        self._write_control_pipe(0x0)
        target_pid = self._read_status_pipe()
        target_status = self._read_status_pipe()
        end_ns = time.monotonic_ns()
        if os.WIFEXITED(target_status):
            exit_code = os.waitstatus_to_exitcode(target_status)
        else:
            exit_code = target_status

        bitmap = self.shm.read()
        return TestResult(test, exit_code, bitmap_to_set(bitmap), end_ns - start_ns)

    def _read_status_pipe(self):
        raw = os.read(self.fsrv_st_fd, 4)
        return int.from_bytes(raw, byteorder="little", signed=False)

    def _write_control_pipe(self, value: int):
        val_bytes = value.to_bytes(4, byteorder="little", signed=False)
        os.write(self.fsrv_ctl_fd, val_bytes)


if __name__ == "__main__":
    qa = QemuAfl("./fuzzme @@")
    qa(b"ok")
    qa(b"bug")
