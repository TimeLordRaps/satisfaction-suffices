from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.request import urlopen

DEFAULT_EXPERTS: tuple[str, ...] = ("proof", "code", "math", "domain_blend")


@dataclass(frozen=True)
class BridgeSource:
    dataset_id: str
    source_file: str
    preferred_experts: tuple[str, ...]
    bridge_weight: float = 1.0
    requires_markdown: bool = True


IKM_SOURCE = BridgeSource(
    dataset_id="Severian/Internal-Knowledge-Map",
    source_file="IKM5-Full.jsonl",
    preferred_experts=DEFAULT_EXPERTS,
    bridge_weight=1.0,
)

IKM_RP_SOURCE = BridgeSource(
    dataset_id="Severian/Internal-Knowledge-Map-StoryWriter-RolePlaying",
    source_file="IKM-RP-Full-v1.jsonl",
    preferred_experts=("domain_blend",),
    bridge_weight=1.15,
)

BRIDGE_SOURCES: dict[str, BridgeSource] = {
    IKM_SOURCE.dataset_id: IKM_SOURCE,
    IKM_RP_SOURCE.dataset_id: IKM_RP_SOURCE,
}

_SYSTEM_MARKER = re.compile(r"(?im)^##\s*system\b")
_INSTRUCTION_MARKER = re.compile(r"(?im)^##\s*instruction\b")
_RESPONSE_MARKER = re.compile(r"(?im)^(?:####|###|##)\s*response\b")


@dataclass(frozen=True)
class BridgeExample:
    dataset_id: str
    source_file: str
    system: str
    instruction: str
    response: str
    preferred_experts: tuple[str, ...]
    bridge_weight: float = 1.0
    requires_markdown: bool = True
    bridge_stage: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return format_bridge_markdown(
            system=self.system,
            instruction=self.instruction,
            response=self.response,
            dataset_id=self.dataset_id,
            tags=self.tags,
        )

    @property
    def sequence_length_hint(self) -> int:
        return max(1, len(self.text.split()))

    def to_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["text"] = self.text
        payload["sequence_length_hint"] = self.sequence_length_hint
        payload["primary_expert"] = assign_bridge_expert(self)
        return payload


@dataclass(frozen=True)
class ExpertPackPlan:
    expert: str
    n_examples: int
    padded_examples: int
    pad_added: int
    estimated_tokens: int


@dataclass(frozen=True)
class DiagonalPackPlan:
    experts: list[ExpertPackPlan]
    pad_multiple: int
    total_examples: int
    total_padded_examples: int
    total_estimated_tokens: int
    imbalance_ratio: float

    def to_record(self) -> dict[str, Any]:
        return {
            "pad_multiple": self.pad_multiple,
            "total_examples": self.total_examples,
            "total_padded_examples": self.total_padded_examples,
            "total_estimated_tokens": self.total_estimated_tokens,
            "imbalance_ratio": self.imbalance_ratio,
            "experts": [asdict(expert) for expert in self.experts],
        }


def format_bridge_markdown(
    *,
    system: str,
    instruction: str,
    response: str,
    dataset_id: str,
    tags: Sequence[str] = (),
) -> str:
    tag_text = " ".join(f"#{tag}" for tag in tags)
    pieces = [
        f"## Bridge Source\n{dataset_id}",
        "## System\n" + system.strip(),
        "## Instruction\n" + instruction.strip(),
        "## Response\n" + response.strip(),
    ]
    if tag_text:
        pieces.append("## Tags\n" + tag_text)
    return "\n\n".join(piece for piece in pieces if piece.strip())


def build_bridge_examples(
    records: Iterable[dict[str, Any]],
    source: BridgeSource,
) -> list[BridgeExample]:
    examples: list[BridgeExample] = []
    for record in records:
        examples.append(parse_bridge_record(record, source=source))
    return examples


def parse_bridge_record(record: dict[str, Any], *, source: BridgeSource) -> BridgeExample:
    system = _lookup_text(record, "system")
    instruction = _lookup_text(record, "instruction", "prompt", "input")
    response = _lookup_text(record, "response", "output", "answer", "completion")

    blob = _lookup_text(record, "text", "content", "markdown", "record")
    if blob and (not system or not instruction or not response):
        system2, instruction2, response2 = _split_markdown_sections(blob)
        system = system or system2
        instruction = instruction or instruction2
        response = response or response2

    if not system:
        system = (
            "Use markdown rigor, preserve internal map links, and keep the bridge-stage "
            "context aligned with system/instruction/response structure."
        )

    if not instruction or not response:
        raise ValueError(
            f"Unable to parse bridge record for {source.dataset_id}; expected system/instruction/response structure"
        )

    tags = _infer_tags(source.dataset_id)
    return BridgeExample(
        dataset_id=source.dataset_id,
        source_file=source.source_file,
        system=system,
        instruction=instruction,
        response=response,
        preferred_experts=source.preferred_experts,
        bridge_weight=source.bridge_weight,
        requires_markdown=source.requires_markdown,
        tags=tags,
    )


def assign_bridge_expert(
    example: BridgeExample,
    expert_names: Sequence[str] = DEFAULT_EXPERTS,
) -> str:
    candidates = [expert for expert in example.preferred_experts if expert in expert_names]
    if not candidates:
        return "domain_blend" if "domain_blend" in expert_names else expert_names[0]
    if len(candidates) == 1:
        return candidates[0]
    digest = hashlib.sha256(example.instruction.encode("utf-8")).digest()
    return candidates[digest[0] % len(candidates)]


def bucket_bridge_examples(
    examples: Sequence[BridgeExample],
    expert_names: Sequence[str] = DEFAULT_EXPERTS,
) -> dict[str, list[BridgeExample]]:
    buckets = {expert: [] for expert in expert_names}
    for example in examples:
        buckets[assign_bridge_expert(example, expert_names)].append(example)
    return buckets


def build_diagonal_pack_plan(
    buckets: dict[str, Sequence[BridgeExample]],
    *,
    pad_multiple: int = 16,
) -> DiagonalPackPlan:
    if pad_multiple < 1:
        raise ValueError("pad_multiple must be >= 1")

    expert_plans: list[ExpertPackPlan] = []
    counts: list[int] = []
    total_examples = 0
    total_padded = 0
    total_tokens = 0

    for expert, examples in buckets.items():
        n_examples = len(examples)
        padded_examples = _round_up(n_examples, pad_multiple)
        estimated_tokens = sum(example.sequence_length_hint for example in examples)
        expert_plans.append(
            ExpertPackPlan(
                expert=expert,
                n_examples=n_examples,
                padded_examples=padded_examples,
                pad_added=padded_examples - n_examples,
                estimated_tokens=estimated_tokens,
            )
        )
        counts.append(n_examples)
        total_examples += n_examples
        total_padded += padded_examples
        total_tokens += estimated_tokens

    non_zero_counts = [count for count in counts if count > 0]
    imbalance_ratio = 1.0
    if non_zero_counts:
        imbalance_ratio = max(non_zero_counts) / min(non_zero_counts)

    return DiagonalPackPlan(
        experts=expert_plans,
        pad_multiple=pad_multiple,
        total_examples=total_examples,
        total_padded_examples=total_padded,
        total_estimated_tokens=total_tokens,
        imbalance_ratio=imbalance_ratio,
    )


def load_jsonl(path_or_url: str) -> Iterator[dict[str, Any]]:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        with urlopen(path_or_url) as response:  # noqa: S310 - explicit user-supplied URL for dataset fetch
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line:
                    yield json.loads(line)
        return

    with Path(path_or_url).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_bridge_outputs(
    *,
    ikm_path: str,
    ikm_rp_path: str,
    out_path: str,
    plan_path: str,
    pad_multiple: int = 16,
    limit_per_source: int | None = None,
) -> dict[str, Any]:
    ikm_records = _limit_records(load_jsonl(ikm_path), limit_per_source)
    rp_records = _limit_records(load_jsonl(ikm_rp_path), limit_per_source)

    examples = build_bridge_examples(ikm_records, IKM_SOURCE)
    examples.extend(build_bridge_examples(rp_records, IKM_RP_SOURCE))

    buckets = bucket_bridge_examples(examples)
    plan = build_diagonal_pack_plan(buckets, pad_multiple=pad_multiple)

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_record(), ensure_ascii=False) + "\n")

    plan_file = Path(plan_path)
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps(plan.to_record(), indent=2) + "\n", encoding="utf-8")

    return {
        "examples_written": len(examples),
        "plan": plan.to_record(),
        "output": str(out_file),
        "plan_output": str(plan_file),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build bridge-stage JSONL and diagonal-pack plan from IKM datasets.")
    parser.add_argument("--ikm", required=True, help="Path or URL for IKM5-Full.jsonl")
    parser.add_argument("--ikm-rp", required=True, help="Path or URL for IKM-RP-Full-v1.jsonl")
    parser.add_argument("--out", default="data/bridge_stage.jsonl", help="Output JSONL path")
    parser.add_argument("--plan-out", default="data/bridge_stage_plan.json", help="Output plan JSON path")
    parser.add_argument("--pad-multiple", type=int, default=16, help="Pad multiple for diagonal-pack planning")
    parser.add_argument("--limit-per-source", type=int, default=None, help="Optional row cap per source for smoke runs")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = write_bridge_outputs(
        ikm_path=args.ikm,
        ikm_rp_path=args.ikm_rp,
        out_path=args.out,
        plan_path=args.plan_out,
        pad_multiple=args.pad_multiple,
        limit_per_source=args.limit_per_source,
    )
    print(json.dumps(result, indent=2))
    return 0


def _infer_tags(dataset_id: str) -> tuple[str, ...]:
    if dataset_id == IKM_SOURCE.dataset_id:
        return ("bridge", "markdown", "knowledge_map")
    return ("bridge", "markdown", "roleplay")


def _limit_records(
    records: Iterator[dict[str, Any]],
    limit: int | None,
) -> list[dict[str, Any]]:
    if limit is None:
        return list(records)
    output: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if index >= limit:
            break
        output.append(record)
    return output


def _lookup_text(record: dict[str, Any], *candidates: str) -> str:
    lowered = {str(key).lower(): value for key, value in record.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return _stringify(lowered[candidate.lower()])
    return ""


def _split_markdown_sections(blob: str) -> tuple[str, str, str]:
    normalized = blob.replace("\r\n", "\n")
    system_match = _SYSTEM_MARKER.search(normalized)
    instruction_match = _INSTRUCTION_MARKER.search(normalized)
    response_match = _RESPONSE_MARKER.search(normalized)

    if not instruction_match or not response_match:
        return "", "", ""

    system = ""
    if system_match:
        system = normalized[system_match.end():instruction_match.start()].strip()

    instruction = normalized[instruction_match.end():response_match.start()].strip()
    response = normalized[response_match.end():].strip()
    return _strip_heading_lines(system), _strip_heading_lines(instruction), _strip_heading_lines(response)


def _strip_heading_lines(value: str) -> str:
    lines = value.splitlines()
    while lines and re.match(r"^\s*#+\s*", lines[0]):
        lines.pop(0)
    return "\n".join(lines).strip()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(_stringify(item) for item in value if item is not None).strip()
    return str(value).strip()


def _round_up(value: int, multiple: int) -> int:
    if value == 0:
        return 0
    return ((value + multiple - 1) // multiple) * multiple


if __name__ == "__main__":
    raise SystemExit(main())
