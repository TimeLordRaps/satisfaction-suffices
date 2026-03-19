from __future__ import annotations

from satisfaction_suffices.bridge import (
    IKM_RP_SOURCE,
    IKM_SOURCE,
    build_bridge_examples,
    build_diagonal_pack_plan,
    bucket_bridge_examples,
    parse_bridge_record,
)


def test_parse_direct_bridge_record() -> None:
    record = {
        "system": "System body",
        "instruction": "Explain the bridge stage.",
        "response": "It sits before MoE gating.",
    }
    example = parse_bridge_record(record, source=IKM_SOURCE)
    assert example.system == "System body"
    assert example.instruction == "Explain the bridge stage."
    assert example.response == "It sits before MoE gating."
    assert example.bridge_stage is True


def test_parse_markdown_blob_bridge_record() -> None:
    record = {
        "text": "## System\nKeep markdown.\n\n## Instruction\n#### Prompt:\nRoute this sample.\n\n#### Response:\nUse the bridge mix.",
    }
    example = parse_bridge_record(record, source=IKM_SOURCE)
    assert "Keep markdown." in example.system
    assert "Route this sample." in example.instruction
    assert "Use the bridge mix." in example.response


def test_roleplay_source_routes_to_domain_blend() -> None:
    examples = build_bridge_examples(
        [
            {
                "system": "Story system",
                "instruction": "Write a roleplay exchange.",
                "response": "Character voice preserved.",
            }
        ],
        IKM_RP_SOURCE,
    )
    buckets = bucket_bridge_examples(examples)
    assert len(buckets["domain_blend"]) == 1
    assert sum(len(bucket) for bucket in buckets.values()) == 1


def test_diagonal_pack_plan_pads_each_bucket() -> None:
    examples = build_bridge_examples(
        [
            {"system": "s1", "instruction": "i1", "response": "r1"},
            {"system": "s2", "instruction": "i2", "response": "r2"},
            {"system": "s3", "instruction": "i3", "response": "r3"},
        ],
        IKM_SOURCE,
    )
    buckets = bucket_bridge_examples(examples)
    plan = build_diagonal_pack_plan(buckets, pad_multiple=4)
    assert plan.total_examples == 3
    assert plan.total_padded_examples >= 3
    assert plan.pad_multiple == 4
    assert all(expert.padded_examples % 4 == 0 or expert.padded_examples == 0 for expert in plan.experts)
