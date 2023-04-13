import angr
import claripy


def main():
    proj = angr.Project("./wasm3", auto_load_libs=True, use_sim_procedures=False)

    payload = b"AAAAAAAA"
    sym_bytes = [claripy.BVS(f"byte_{i}", 8) for i in range(len(payload))]
    sym_payload = claripy.Concat(*sym_bytes)

    input_file = angr.SimFile("/tmp/payload", content=sym_payload)

    state = proj.factory.entry_state(
        args=["./wasm3", "/tmp/payload"],
        fs={
            "/tmp/payload": input_file
        },
        add_options={angr.options.ZERO_FILL_UNCONSTRAINED_MEMORY,
                     angr.options.USE_SYSTEM_TIMES}
    )

    payload_constraints = []
    for i in range(len(payload)):
        constraint = sym_bytes[i] == payload[i]
        state.solver.add(constraint)
        payload_constraints.append(constraint)

    simgr = proj.factory.simgr(state)
    simgr.use_technique(angr.exploration_techniques.DFS())

    while True:
        simgr.step()
        print(simgr)
        try:
            deadend = simgr.deadended[0]
            observed_constraints = list(deadend.solver.constraints.copy())
            for c in payload_constraints:
                observed_constraints.remove(c)
            break
        except IndexError:
            pass

    print(observed_constraints)

    new_payloads = set()

    for i in range(len(observed_constraints)):
        tmp_constraints = observed_constraints.copy()
        tmp_constraints = claripy.Not(tmp_constraints[i])
        solver = claripy.Solver()
        solver.add(tmp_constraints)

        np = bytearray()
        for sb in sym_bytes:
            b = solver.eval(sb, 1)[0]
            np.append(b)
        new_payloads.add(bytes(np))

    for np in new_payloads:
        print(np)

main()
