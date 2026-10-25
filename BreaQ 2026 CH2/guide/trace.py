focus = "SCAN-B"
trace = service.trace(workloads[focus])
for snapshot in trace:
    print(snapshot["stage"], "depth=", snapshot["depth"], "ops=", snapshot["operations"])

# Available for inspection, but no fault labels are supplied:
# print(trace[index]["circuit"].draw(output="text"))

# Look at the rz sign after the phase stage (02) and after the vendor stage (03).
for s in trace:
    if s["stage"][:2] in ("02", "03"):
        print(s["stage"]); print(s["circuit"].draw(output="text"))
