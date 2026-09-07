# Manchester state-delay pilot

Launched on the Mac on 7 September 2026 using merged evaluator commit
`908bd10f86542de94fc38af90dd56c2ccc08cf9b` and the recorded CPU runtime.

This is one fleet draw (seed 1), with five serial conditions: fresh per-task,
100 ms, 500 ms, 1,000 ms, and ingress DLA. Each full condition replays the
3,600-second Manchester incident trace. A ten-step ingress preflight runs
first. The other modes already have source-hash-bound short validation.

- `manifest.json`: fixed inputs, versions, controls, comparisons and limits.
- `status.json`: current condition, worker PID, elapsed time and completed cells.
- `pilot.log`: launches, completed validations and any failure details.
- `cells/`: each condition's summary, step/task arrays, logs and validation.
- `RESULTS.md` and `comparison.csv`: created automatically when all five pass.

The runner preserves attempts, stops on any failure, and prevents concurrent
copies through a file lock. It skips only validated, checksum-matching cells
when resumed. It cannot resume midway through a 3,600-step evaluator call;
an interrupted cell starts again in a new attempt directory.

After an interruption has been investigated, resume with:

```sh
caffeinate -is \
  /Users/akashx/Downloads/diss_mat/vec_env-state-delay/.venv/bin/python -u \
  /Users/akashx/Downloads/diss_mat/state-delay-pilot-2026-09-07/run_pilot.py --resume
```

To stop, send SIGTERM to the runner `pid` recorded in `status.json`. The
runner terminates its current evaluator and retains outputs. Do not edit the
manifest, runner, frozen code or inputs while the pilot is running.

Keep the Mac connected to power with its lid open. Caffeinate prevents idle
sleep but cannot protect against shutdown, power loss or closing the lid.

Results are descriptive for one fleet draw. Placement uses older workload
reports; admission and acknowledgements remain current. The timing model
retains once-per-second admission batches with continuous service between
them. Equal reports during idle periods do not establish general resilience
to communication delay. See the evaluator's `docs/RSU_STATE_DELAY.md`.
