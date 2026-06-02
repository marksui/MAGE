import json
import tempfile
from pathlib import Path

from mage.debug_memory import DebugMemory
from mage.utils import reformat_json_string


def main():
    sim_log = json.dumps(
        {
            "stdout": (
                "Hint: Output 'out' has 3 mismatches. "
                "First mismatch occurred at time 42.\n"
                "Hint: Total mismatched samples is 3 out of 10 samples\n"
                "Mismatches: 3 in 10 samples\n"
            ),
            "stderr": "",
        }
    )
    memory = DebugMemory()
    checkpoint = memory.add_checkpoint(
        stage="rtl_candidate_1",
        rtl_code="module TopModule; endmodule",
        sim_log=sim_log,
        is_syntax_pass=True,
        is_sim_pass=False,
    )

    assert checkpoint.mismatch_count == 3
    assert checkpoint.first_mismatch_time == 42
    assert checkpoint.output_mismatches[0].output_name == "out"
    assert checkpoint.cost == 3
    prompt_text = memory.format_for_prompt()
    assert "rtl_candidate_1" in prompt_text
    assert "Best checkpoint so far" in prompt_text
    memory_dict = memory.to_dict()
    assert memory_dict["checkpoint_count"] == 1
    assert memory_dict["best_checkpoint"]["mismatch_count"] == 3
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir) / "debug_memory.json"
        memory.write_json(str(memory_path))
        exported = json.loads(memory_path.read_text(encoding="utf-8"))
        assert exported["checkpoints"][0]["stage"] == "rtl_candidate_1"

    fenced_json = """```json
{"reasoning": "ok", "module": "module top; assign y = a ? b : c; endmodule"}
```"""
    assert reformat_json_string(fenced_json).startswith('{"reasoning"')

    prefixed_json = (
        "Here is the answer:\n"
        '{"reasoning": "ok", "module": "module top; endmodule"}\n'
        "Done."
    )
    assert reformat_json_string(prefixed_json).endswith('endmodule"}')


if __name__ == "__main__":
    main()
