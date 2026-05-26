import json

from mage.debug_memory import DebugMemory


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


if __name__ == "__main__":
    main()
