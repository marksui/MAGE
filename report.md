# MAGE Change Summary

## Changes

- Added `DebugMemory` to track checkpoints, mismatches, error context, and repair actions.
- Passed memory summaries through `agent.py` to `SimJudge` and `RTLEditor`.
- Added tests for checkpoint recording and memory summaries.
- Hardened fenced JSON parsing, Windows simulation commands, and the `Prob093_ece241_2014_q3` mux mapping prompt.

## Modified Files

- `src/mage/debug_memory.py`
- `src/mage/agent.py`
- `src/mage/sim_judge.py`
- `src/mage/rtl_editor.py`
- `src/mage/utils.py`
- `src/mage/bash_tools.py`
- `src/mage/rtl_generator.py`
- `tests/test_debug_memory.py`
