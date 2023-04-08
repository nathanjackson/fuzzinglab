#!/usr/bin/env python

import os
import signal
import sys

import sysv_ipc


FORKSRV_FD = 198

def main():
    map_size = 1 << 16
    shm = sysv_ipc.SharedMemory(sysv_ipc.IPC_PRIVATE, size=map_size)

    st_pipe = os.pipe()
    ctl_pipe = os.pipe()

    fsrv_pid = os.fork()

    if not fsrv_pid:
        # setup control and status pipes
        os.dup2(ctl_pipe[0], FORKSRV_FD)
        os.dup2(st_pipe[1], FORKSRV_FD + 1)

        # close original fds
        os.close(st_pipe[0])
        os.close(st_pipe[1])
        os.close(ctl_pipe[0])
        os.close(ctl_pipe[1])

        # exec
        os.execle(
            "./qemu/build/qemu-x86_64",
            "./qemu/build/qemu-x86_64",
            "/bin/ls",
            { "__AFL_SHM_ID": str(shm.id),
              "AFL_DEBUG": "1" }
        )

        print("Exec Failed!")
        sys.exit(0)

    os.close(ctl_pipe[0])
    os.close(st_pipe[1])

    fsrv_ctl_fd = ctl_pipe[1]
    fsrv_st_fd = st_pipe[0]

    # read status for hello
    status = int.from_bytes(os.read(fsrv_st_fd, 4), byteorder="little")
    print("[INFO] forkserver is up!")

    # signal forkserver - this runs the target binary
    os.write(fsrv_ctl_fd, b"\x00\x00\x00\x00")

    # get target pid
    child_pid = int.from_bytes(os.read(fsrv_st_fd, 4), byteorder="little")
    print("[INFO] child pid =", child_pid)

    # read child status
    child_status = int.from_bytes(os.read(fsrv_st_fd, 4), byteorder="little")
    print("[INFO] child status =", child_status)

    # signal forkserver - this runs the target binary
    os.write(fsrv_ctl_fd, b"\x00\x00\x00\x00")

    # get target pid
    child_pid = int.from_bytes(os.read(fsrv_st_fd, 4), byteorder="little")
    print("[INFO] child pid =", child_pid)

    # read child status
    child_status = int.from_bytes(os.read(fsrv_st_fd, 4), byteorder="little")
    print("[INFO] child status =", child_status)


    # wait for the forkserver to terminate
    os.kill(fsrv_pid, signal.SIGTERM)
    pid, status = os.waitpid(fsrv_pid, 0)


main()
