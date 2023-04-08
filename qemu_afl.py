import subprocess
import tempfile

import sysv_ipc


def bitmap_to_set(m):
    res = set()
    bit = 0
    for byte in m:
        for i in range(8):
            if (byte >> i) & 0x1:
                res.add(bit)
            bit += 1
    return res


class QemuAfl:
    def __init__(self, cmd):
        self.args = cmd.split()
        self.replace_index = self.args.index("@@")
        map_size = 1 << 16
        self._shm = sysv_ipc.SharedMemory(sysv_ipc.IPC_PRIVATE, size=map_size)
        self.last_coverage = set()
        self.lifetime_coverage = set()

    def exec(self, a):
        args = ["./qemu/build/qemu-x86_64"]
        args += a
        self._shm.write(bytes([0 for _ in range(self._shm.size)]))
        completed = subprocess.run(args, env={
            "__AFL_SHM_ID": str(self._shm.id),
        })
        crashed = False
        if (completed.returncode & 0xFFFFFFFF) > 128:
            crashed = True
        return crashed, self._shm.read(self._shm.size)

    def __call__(self, test):
        with tempfile.NamedTemporaryFile("wb") as payload:
            payload.write(test)
            payload.flush()
            a = self.args.copy()
            a[self.replace_index] = payload.name
            crashed, bitmap = self.exec(a)
        self.last_coverage = bitmap_to_set(bitmap)
        self.lifetime_coverage.update(self.last_coverage)
        return crashed


if __name__ == "__main__":
    qa = QemuAfl("./fuzzme @@")
    qa(b"ok")
    qa(b"bug")
