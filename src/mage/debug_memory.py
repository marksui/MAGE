import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OutputMismatch:
    output_name: str
    mismatch_count: int
    first_mismatch_time: int | None = None


@dataclass
class StateCheckpoint:
    iteration: int
    stage: str
    rtl_digest: str
    rtl_code: str
    tb_digest: str | None = None
    is_syntax_pass: bool | None = None
    is_sim_pass: bool | None = None
    mismatch_count: int | None = None
    first_mismatch_time: int | None = None
    output_mismatches: list[OutputMismatch] = field(default_factory=list)
    mismatch_lines: list[str] = field(default_factory=list)
    action: str | None = None
    notes: str = ""
    sim_log_excerpt: str = ""
    cost: float = 0.0


class DebugMemory:
    """In-memory state checkpoints for one benchmark instance."""

    def __init__(self) -> None:
        self.checkpoints: list[StateCheckpoint] = []

    @staticmethod
    def digest(content: str) -> str:
        return hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()[:12]

    @staticmethod
    def _extract_command_output(sim_log: str) -> tuple[str, str]:
        try:
            parsed = json.loads(sim_log)
        except (TypeError, json.JSONDecodeError):
            return sim_log, ""
        if isinstance(parsed, dict):
            return str(parsed.get("stdout", "")), str(parsed.get("stderr", ""))
        return str(parsed), ""

    @classmethod
    def parse_sim_log(cls, sim_log: str) -> dict[str, Any]:
        stdout, stderr = cls._extract_command_output(sim_log)
        combined = "\n".join(part for part in [stdout, stderr] if part)

        output_mismatches: list[OutputMismatch] = []
        for output_name, count, first_time in re.findall(
            r"Hint: Output '([^']+)' has (\d+) mismatches\. "
            r"First mismatch occurred at time (\d+)\.",
            combined,
        ):
            output_mismatches.append(
                OutputMismatch(
                    output_name=output_name,
                    mismatch_count=int(count),
                    first_mismatch_time=int(first_time),
                )
            )

        mismatch_count: int | None = None
        mismatch_patterns = [
            r"Mismatches:\s*(\d+)\s+in\s+\d+\s+samples",
            r"Total mismatched samples is\s+(\d+)",
            r"SIMULATION FAILED\s*-\s*(\d+)\s+MISMATCHES DETECTED",
        ]
        for pattern in mismatch_patterns:
            match = re.search(pattern, combined)
            if match:
                mismatch_count = int(match.group(1))
                break
        if mismatch_count is None and output_mismatches:
            mismatch_count = sum(item.mismatch_count for item in output_mismatches)

        first_mismatch_time: int | None = None
        first_times = [
            item.first_mismatch_time
            for item in output_mismatches
            if item.first_mismatch_time is not None
        ]
        if first_times:
            first_mismatch_time = min(first_times)
        else:
            match = re.search(r"First mismatch occurred at time\s+(\d+)", combined)
            if match:
                first_mismatch_time = int(match.group(1))

        mismatch_lines = [
            line.strip()
            for line in combined.splitlines()
            if any(
                keyword in line.lower()
                for keyword in ["mismatch", "expected", "actual", "time"]
            )
        ][:8]

        return {
            "mismatch_count": mismatch_count,
            "first_mismatch_time": first_mismatch_time,
            "output_mismatches": output_mismatches,
            "mismatch_lines": mismatch_lines,
            "combined_log": combined,
        }

    @staticmethod
    def compute_cost(
        is_syntax_pass: bool | None,
        is_sim_pass: bool | None,
        mismatch_count: int | None,
    ) -> float:
        if is_sim_pass:
            return 0.0
        if is_syntax_pass is False:
            return 1_000_000.0
        if mismatch_count is not None:
            return float(mismatch_count)
        return 100_000.0

    def add_checkpoint(
        self,
        stage: str,
        rtl_code: str,
        testbench: str | None = None,
        sim_log: str = "",
        is_syntax_pass: bool | None = None,
        is_sim_pass: bool | None = None,
        mismatch_count: int | None = None,
        action: str | None = None,
        notes: str = "",
    ) -> StateCheckpoint:
        parsed = self.parse_sim_log(sim_log)
        mismatch_count = (
            mismatch_count
            if mismatch_count is not None
            else parsed["mismatch_count"]
        )
        checkpoint = StateCheckpoint(
            iteration=len(self.checkpoints) + 1,
            stage=stage,
            rtl_digest=self.digest(rtl_code),
            rtl_code=rtl_code,
            tb_digest=self.digest(testbench) if testbench is not None else None,
            is_syntax_pass=is_syntax_pass,
            is_sim_pass=is_sim_pass,
            mismatch_count=mismatch_count,
            first_mismatch_time=parsed["first_mismatch_time"],
            output_mismatches=parsed["output_mismatches"],
            mismatch_lines=parsed["mismatch_lines"],
            action=action,
            notes=notes,
            sim_log_excerpt=parsed["combined_log"][:1200],
            cost=self.compute_cost(is_syntax_pass, is_sim_pass, mismatch_count),
        )
        self.checkpoints.append(checkpoint)
        return checkpoint

    def best_checkpoint(self) -> StateCheckpoint | None:
        if not self.checkpoints:
            return None
        return min(self.checkpoints, key=lambda checkpoint: checkpoint.cost)

    @staticmethod
    def _mismatch_to_dict(mismatch: OutputMismatch) -> dict[str, Any]:
        return {
            "output_name": mismatch.output_name,
            "mismatch_count": mismatch.mismatch_count,
            "first_mismatch_time": mismatch.first_mismatch_time,
        }

    def checkpoint_to_dict(self, checkpoint: StateCheckpoint) -> dict[str, Any]:
        return {
            "iteration": checkpoint.iteration,
            "stage": checkpoint.stage,
            "rtl_digest": checkpoint.rtl_digest,
            "tb_digest": checkpoint.tb_digest,
            "is_syntax_pass": checkpoint.is_syntax_pass,
            "is_sim_pass": checkpoint.is_sim_pass,
            "mismatch_count": checkpoint.mismatch_count,
            "first_mismatch_time": checkpoint.first_mismatch_time,
            "output_mismatches": [
                self._mismatch_to_dict(item)
                for item in checkpoint.output_mismatches
            ],
            "mismatch_lines": checkpoint.mismatch_lines,
            "action": checkpoint.action,
            "notes": checkpoint.notes,
            "sim_log_excerpt": checkpoint.sim_log_excerpt,
            "cost": checkpoint.cost,
        }

    def to_dict(self) -> dict[str, Any]:
        best = self.best_checkpoint()
        return {
            "checkpoint_count": len(self.checkpoints),
            "best_checkpoint": (
                self.checkpoint_to_dict(best) if best is not None else None
            ),
            "checkpoints": [
                self.checkpoint_to_dict(checkpoint)
                for checkpoint in self.checkpoints
            ],
        }

    def write_json(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def format_for_prompt(self, max_entries: int = 6) -> str:
        if not self.checkpoints:
            return "No state checkpoints have been recorded yet."

        lines = [
            "State checkpoint memory for this debug run:",
            "Use this to avoid repeating failed updates, prefer lower-cost states, "
            "and backtrack if a new edit increases cost.",
        ]
        best = self.best_checkpoint()
        if best:
            lines.append(
                "Best checkpoint so far: "
                f"#{best.iteration} stage={best.stage}, cost={best.cost:g}, "
                f"mismatches={best.mismatch_count}, "
                f"first_mismatch_time={best.first_mismatch_time}, "
                f"rtl_digest={best.rtl_digest}."
            )

        for checkpoint in self.checkpoints[-max_entries:]:
            output_summary = ", ".join(
                f"{item.output_name}:{item.mismatch_count}@{item.first_mismatch_time}"
                for item in checkpoint.output_mismatches
            )
            if not output_summary:
                output_summary = "none"
            lines.append(
                f"- #{checkpoint.iteration} {checkpoint.stage}: "
                f"syntax={checkpoint.is_syntax_pass}, sim={checkpoint.is_sim_pass}, "
                f"mismatches={checkpoint.mismatch_count}, "
                f"first_t={checkpoint.first_mismatch_time}, "
                f"cost={checkpoint.cost:g}, rtl={checkpoint.rtl_digest}, "
                f"outputs={output_summary}."
            )
            if checkpoint.action:
                lines.append(f"  action: {checkpoint.action[:300]}")
            if checkpoint.notes:
                lines.append(f"  notes: {checkpoint.notes[:300]}")
            if checkpoint.mismatch_lines:
                lines.append(
                    "  mismatch evidence: "
                    + " | ".join(checkpoint.mismatch_lines[:3])[:500]
                )
        return "\n".join(lines)
