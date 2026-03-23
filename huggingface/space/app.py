"""
Satisfaction Suffices — Live Verification Demo
================================================
SAT-gated structural containment for AI.
No-code block composer for proof and program discovery.
Search tree visualization for proof evolution.
"""

import html as html_mod
from collections import defaultdict

import gradio as gr
from satisfaction_suffices import verify, evolve_proof, Verdict

# ── Constants ────────────────────────────────────────────────────────────────

DOMAIN_CHOICES = [
    "logic", "code", "math", "proof", "text",
    "med", "law", "bio", "cyber", "chem", "quantum", "philosophy",
]

VERDICT_COLORS = {
    Verdict.VERIFIED: "#22c55e",
    Verdict.CONTRADICTION: "#ef4444",
    Verdict.PARADOX: "#f59e0b",
    Verdict.TIMEOUT: "#6b7280",
}

VERDICT_LABELS = {
    Verdict.VERIFIED: "VERIFIED",
    Verdict.CONTRADICTION: "CONTRADICTION",
    Verdict.PARADOX: "PARADOX",
    Verdict.TIMEOUT: "TIMEOUT",
}

# ── Block Composer: Logic Primitives ─────────────────────────────────────────

LOGIC_BLOCKS = {
    "IF ... THEN ...": "if {A} then {B}",
    "AND": "{A} AND {B}",
    "OR": "{A} OR {B}",
    "NOT": "NOT {A}",
    "IF AND ONLY IF": "{A} if and only if {B}",
    "IMPLIES (chain)": "if {A} then {B}. if {B} then {C}",
    "CONTRADICTION": "{A}. NOT {A}",
    "EXCLUSIVE OR": "({A} OR {B}). NOT ({A} AND {B})",
    "MUTUAL EXCLUSION": "{A} AND {B}",
    "COMPLETENESS": "{A} AND {B}",
    "CONDITIONAL DEP": "if {A} then {B}. {A}. NOT {B}",
    "FORALL (bounded)": "for all x: if {A}(x) then {B}(x)",
    "EXISTS": "there exists x such that {A}(x)",
    "PIGEONHOLE": "if n+1 items in n boxes then some box has 2",
}

CODE_PATTERN_BLOCKS = {
    "ASSERT precondition": "assert {condition}",
    "ASSERT postcondition": "# post: assert {condition}",
    "INVARIANT (loop)": "while {guard}:\n    assert {invariant}  # maintained each iteration\n    {body}",
    "LOCK acquire/release": "lock.acquire()\ntry:\n    {critical_section}\nfinally:\n    lock.release()",
    "MUTEX ordering": "# Lock ordering: always acquire {lock_A} before {lock_B}\nwith {lock_A}:\n    with {lock_B}:\n        {body}",
    "ATOMIC read-modify-write": "# atomic: read {var}, modify, write back\nold = {var}.load()\n{var}.compare_exchange(old, {new_val})",
    "BOUNDED resource": "assert len({resource}) <= {max_size}",
    "NULL safety": "assert {ptr} is not None\n{ptr}.{method}()",
    "TYPE guard": "assert isinstance({obj}, {expected_type})",
    "TRANSFER (financial)": "def transfer(amount, balance):\n    assert amount > 0\n    assert amount <= balance\n    return balance - amount",
}

META_CLAUSE_BLOCKS = {
    "Non-empty (existence)": "{field} must not be empty",
    "Bounded length": "len({field}) <= {max_len}",
    "No null bytes (transport)": "{field} contains no null bytes",
    "UTF-8 valid (encoding)": "{field} is valid UTF-8",
    "Mutual exclusion": "{state_A} and {state_B} cannot both be true",
    "Completeness": "{field_A} and {field_B} must both exist",
    "Temporal ordering": "{event_A} must occur before {event_B}",
    "Idempotency": "applying {operation} twice equals applying it once",
    "Consistency": "{state} and NOT {state} cannot coexist",
    "Conditional dependency": "if {condition} then {requirement} must hold",
    "Rate limit": "{operation} at most {N} times per {interval}",
    "Encryption gate": "if {channel} is public then {payload} must be encrypted",
}

# ── Rendering ────────────────────────────────────────────────────────────────

def render_verdict(result) -> str:
    color = VERDICT_COLORS[result.verdict]
    label = VERDICT_LABELS[result.verdict]
    return f"""
    <div style="font-family: monospace; padding: 16px; border: 2px solid {color}; border-radius: 8px; background: #0d1117;">
        <h2 style="color: {color}; margin: 0 0 12px 0;">{label}</h2>
        <table style="color: #c9d1d9; font-size: 14px; border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">SAT Ratio</td>
                <td><strong>{result.sat_ratio:.2%}</strong></td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Zone</td>
                <td>{result.zone}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Constraints</td>
                <td>{result.n_constraints}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Satisfied</td>
                <td>{result.n_satisfied}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Refuted</td>
                <td>{result.n_refuted}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Timeout</td>
                <td>{result.n_timeout}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Paradox</td>
                <td>{result.n_paradox}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Elapsed</td>
                <td>{result.elapsed_ms:.1f} ms</td></tr>
        </table>
    </div>"""


def render_evolution(evo) -> str:
    color = "#22c55e" if evo.resolved else "#ef4444"
    label = "RESOLVED" if evo.resolved else "UNRESOLVED"
    return f"""
    <div style="font-family: monospace; padding: 16px; border: 2px solid {color}; border-radius: 8px; background: #0d1117;">
        <h2 style="color: {color}; margin: 0 0 12px 0;">{label}</h2>
        <table style="color: #c9d1d9; font-size: 14px; border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Best Status</td>
                <td><strong>{evo.best_node.status.name}</strong></td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Generations</td>
                <td>{evo.generations}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Proved</td>
                <td>{evo.proved_count}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Total Nodes</td>
                <td>{evo.total_candidates}</td></tr>
        </table>
    </div>"""


# ── Search Tree / Graph Visualization ────────────────────────────────────────

STATUS_COLORS = {
    "PROVED": "#22c55e",
    "REFUTED": "#ef4444",
    "UNRESOLVED": "#f59e0b",
    "EVOLVING": "#3b82f6",
}


def render_search_tree(evo) -> str:
    """Render the evolution tree as an interactive SVG."""
    tree = evo.evolution_tree
    if not tree:
        return "<p style='color: #6b7280;'>No tree data.</p>"

    # Group nodes by generation
    by_gen = defaultdict(list)
    for node in tree.values():
        by_gen[node.generation].append(node)

    max_gen = max(by_gen.keys()) if by_gen else 0
    max_width = max(len(nodes) for nodes in by_gen.values()) if by_gen else 1

    # Layout constants
    node_r = 22
    h_spacing = max(80, 900 // max(max_width, 1))
    v_spacing = 100
    padding = 60
    svg_w = max(max_width * h_spacing + padding * 2, 500)
    svg_h = (max_gen + 1) * v_spacing + padding * 2

    # Assign (x, y) positions
    positions = {}
    for gen in range(max_gen + 1):
        nodes = sorted(by_gen[gen], key=lambda n: n.id)
        count = len(nodes)
        total_w = (count - 1) * h_spacing if count > 1 else 0
        start_x = (svg_w - total_w) / 2
        for i, node in enumerate(nodes):
            positions[node.id] = (start_x + i * h_spacing, padding + gen * v_spacing)

    # Build SVG
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background: #0d1117; border-radius: 8px; border: 1px solid #30363d;">'
    ]

    # Edges
    for node in tree.values():
        if node.parent_id and node.parent_id in positions and node.id in positions:
            px, py = positions[node.parent_id]
            cx, cy = positions[node.id]
            mutation_label = node.mutations[-1] if node.mutations else ""
            parts.append(
                f'<line x1="{px}" y1="{py + node_r}" x2="{cx}" y2="{cy - node_r}" '
                f'stroke="#30363d" stroke-width="2"/>'
            )
            if mutation_label:
                mx, my = (px + cx) / 2, (py + cy) / 2
                safe_label = html_mod.escape(mutation_label[:18])
                parts.append(
                    f'<text x="{mx}" y="{my - 5}" text-anchor="middle" '
                    f'font-size="9" fill="#6b7280" font-family="monospace">{safe_label}</text>'
                )

    # Nodes
    best_id = evo.best_node.id
    for node in tree.values():
        if node.id not in positions:
            continue
        x, y = positions[node.id]
        color = STATUS_COLORS.get(node.status.name, "#6b7280")
        stroke_w = "3" if node.id == best_id else "1.5"
        stroke_color = "#ffffff" if node.id == best_id else color
        opacity = max(0.3, min(1.0, node.fitness + 0.2))

        safe_stmt = html_mod.escape(node.statement[:200])
        tooltip = f"{node.status.name} | fitness={node.fitness:.2%} | gen={node.generation}\n{safe_stmt}"

        parts.append(f'<g>')
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{node_r}" '
            f'fill="{color}" fill-opacity="{opacity:.2f}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_w}"/>'
        )
        parts.append(
            f'<title>{tooltip}</title>'
        )
        # Fitness label inside node
        parts.append(
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" '
            f'font-size="10" fill="#ffffff" font-family="monospace" font-weight="bold">'
            f'{node.fitness:.0%}</text>'
        )
        # Node ID below
        parts.append(
            f'<text x="{x}" y="{y + node_r + 14}" text-anchor="middle" '
            f'font-size="9" fill="#8b949e" font-family="monospace">{html_mod.escape(node.id)}</text>'
        )
        parts.append(f'</g>')

    # Legend
    legend_y = svg_h - 30
    legend_items = [("PROVED", "#22c55e"), ("REFUTED", "#ef4444"), ("UNRESOLVED", "#f59e0b"), ("EVOLVING", "#3b82f6")]
    for i, (name, col) in enumerate(legend_items):
        lx = 20 + i * 130
        parts.append(f'<circle cx="{lx}" cy="{legend_y}" r="6" fill="{col}"/>')
        parts.append(
            f'<text x="{lx + 12}" y="{legend_y + 4}" font-size="11" fill="#c9d1d9" '
            f'font-family="monospace">{name}</text>'
        )

    # Best node highlight label
    if best_id in positions:
        bx, by = positions[best_id]
        parts.append(
            f'<text x="{bx}" y="{by - node_r - 6}" text-anchor="middle" '
            f'font-size="10" fill="#ffffff" font-family="monospace">BEST</text>'
        )

    parts.append('</svg>')

    # Stats summary below SVG
    stats = f"""
    <div style="font-family: monospace; padding: 12px; color: #c9d1d9; font-size: 13px; margin-top: 8px;">
        <strong>Generations:</strong> {evo.generations} |
        <strong>Total nodes:</strong> {evo.total_candidates} |
        <strong>Proved:</strong> {evo.proved_count} |
        <strong>Refuted:</strong> {evo.refuted_count} |
        <strong>Unresolved:</strong> {evo.unresolved_count} |
        <strong>Diversity:</strong> {evo.diversity:.1%} |
        <strong>Elapsed:</strong> {evo.elapsed_ms:.1f}ms
    </div>"""

    return "\n".join(parts) + stats


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_STATEMENT = "if A then B. if B then C. not C. A."


# ── Tab Handlers ─────────────────────────────────────────────────────────────

def run_verify(content: str, domain: str) -> str:
    if not content.strip():
        return "<p style='color: #6b7280;'>Enter content to verify.</p>"
    return render_verdict(verify(content, domain=domain))


def run_evolve(content: str, max_gens: int) -> str:
    if not content.strip():
        return "<p style='color: #6b7280;'>Enter content to evolve.</p>"
    return render_evolution(evolve_proof(content, max_generations=int(max_gens)))


def run_tree_viz(content: str, max_gens: int, pop_size: int) -> str:
    if not content.strip():
        return "<p style='color: #6b7280;'>Enter content to visualize.</p>"
    evo = evolve_proof(content, max_generations=int(max_gens), population_size=int(pop_size))
    return render_search_tree(evo)


# ── Block Composer Logic ─────────────────────────────────────────────────────

def compose_blocks(
    block1: str, var1a: str, var1b: str, var1c: str,
    block2: str, var2a: str, var2b: str, var2c: str,
    block3: str, var3a: str, var3b: str, var3c: str,
    block4: str, var4a: str, var4b: str, var4c: str,
) -> str:
    """Compose up to 4 logic blocks into a proposition string."""
    clauses = []
    for block, va, vb, vc in [
        (block1, var1a, var1b, var1c),
        (block2, var2a, var2b, var2c),
        (block3, var3a, var3b, var3c),
        (block4, var4a, var4b, var4c),
    ]:
        if block and block != "(none)":
            template = LOGIC_BLOCKS.get(block, block)
            filled = template.replace("{A}", va or "A").replace("{B}", vb or "B").replace("{C}", vc or "C")
            clauses.append(filled)
    return "\n".join(clauses)


def compose_and_verify(
    block1, var1a, var1b, var1c,
    block2, var2a, var2b, var2c,
    block3, var3a, var3b, var3c,
    block4, var4a, var4b, var4c,
):
    composed = compose_blocks(
        block1, var1a, var1b, var1c,
        block2, var2a, var2b, var2c,
        block3, var3a, var3b, var3c,
        block4, var4a, var4b, var4c,
    )
    if not composed.strip():
        return "", "<p style='color: #6b7280;'>Select at least one block.</p>", gr.update()
    result = verify(composed, domain="logic")
    return composed, render_verdict(result), composed


def compose_and_evolve(
    block1, var1a, var1b, var1c,
    block2, var2a, var2b, var2c,
    block3, var3a, var3b, var3c,
    block4, var4a, var4b, var4c,
    max_gens,
):
    composed = compose_blocks(
        block1, var1a, var1b, var1c,
        block2, var2a, var2b, var2c,
        block3, var3a, var3b, var3c,
        block4, var4a, var4b, var4c,
    )
    if not composed.strip():
        return "", "<p style='color: #6b7280;'>Select at least one block.</p>", gr.update()
    evo = evolve_proof(composed, max_generations=int(max_gens))
    return composed, render_evolution(evo), composed


# ── Program Discovery ───────────────────────────────────────────────────────

def compose_program(
    pat1: str, p1a: str, p1b: str,
    pat2: str, p2a: str, p2b: str,
    pat3: str, p3a: str, p3b: str,
    meta1: str, m1a: str, m1b: str,
    meta2: str, m2a: str, m2b: str,
    meta3: str, m3a: str, m3b: str,
):
    """Compose code pattern blocks + meta-clause blocks into a verifiable program."""
    lines = []

    # Code patterns
    for pat, pa, pb in [(pat1, p1a, p1b), (pat2, p2a, p2b), (pat3, p3a, p3b)]:
        if pat and pat != "(none)":
            template = CODE_PATTERN_BLOCKS.get(pat, pat)
            filled = (template
                .replace("{condition}", pa or "x > 0")
                .replace("{guard}", pa or "running")
                .replace("{invariant}", pb or "count >= 0")
                .replace("{body}", pb or "pass")
                .replace("{critical_section}", pa or "shared_state += 1")
                .replace("{lock_A}", pa or "mutex_a")
                .replace("{lock_B}", pb or "mutex_b")
                .replace("{var}", pa or "counter")
                .replace("{new_val}", pb or "old + 1")
                .replace("{resource}", pa or "buffer")
                .replace("{max_size}", pb or "4096")
                .replace("{ptr}", pa or "node")
                .replace("{method}", pb or "process")
                .replace("{obj}", pa or "value")
                .replace("{expected_type}", pb or "int")
            )
            lines.append(filled)

    if lines:
        lines.append("")
        lines.append("# --- Meta-Clauses ---")

    # Meta-clauses
    for meta, ma, mb in [(meta1, m1a, m1b), (meta2, m2a, m2b), (meta3, m3a, m3b)]:
        if meta and meta != "(none)":
            template = META_CLAUSE_BLOCKS.get(meta, meta)
            filled = (template
                .replace("{field}", ma or "message")
                .replace("{field_A}", ma or "sender")
                .replace("{field_B}", mb or "recipient")
                .replace("{max_len}", mb or "4096")
                .replace("{state_A}", ma or "encrypted")
                .replace("{state_B}", mb or "plaintext")
                .replace("{state}", ma or "delivered")
                .replace("{event_A}", ma or "auth")
                .replace("{event_B}", mb or "access")
                .replace("{operation}", ma or "dedup")
                .replace("{condition}", ma or "urgent")
                .replace("{requirement}", mb or "has_ttl")
                .replace("{channel}", ma or "channel")
                .replace("{payload}", mb or "payload")
                .replace("{N}", mb or "100")
                .replace("{interval}", "second")
            )
            lines.append("# META: " + filled)

    composed = "\n".join(lines)
    if not composed.strip():
        return "", "<p style='color: #6b7280;'>Select at least one pattern or meta-clause.</p>", gr.update()
    result = verify(composed, domain="code")
    return composed, render_verdict(result), composed


# ── Block Row Builder ────────────────────────────────────────────────────────

def make_logic_block_row(n: int, block_choices):
    """Create a row of block selector + 3 variable inputs."""
    with gr.Row():
        block = gr.Dropdown(
            choices=["(none)"] + list(block_choices.keys()),
            value="(none)",
            label=f"Block {n}",
            scale=2,
        )
        va = gr.Textbox(label="A", placeholder="variable A", scale=1)
        vb = gr.Textbox(label="B", placeholder="variable B", scale=1)
        vc = gr.Textbox(label="C", placeholder="variable C", scale=1)
    return block, va, vb, vc


def make_pattern_row(n: int, choices, row_label="Pattern"):
    with gr.Row():
        pat = gr.Dropdown(
            choices=["(none)"] + list(choices.keys()),
            value="(none)",
            label=f"{row_label} {n}",
            scale=2,
        )
        pa = gr.Textbox(label="Param 1", placeholder="condition / name", scale=1)
        pb = gr.Textbox(label="Param 2", placeholder="value / bound", scale=1)
    return pat, pa, pb


# ── Examples ─────────────────────────────────────────────────────────────────

EXAMPLES_UNIVERSAL = [
    ["if A then B. if B then C. not C. A."],
    ["A. not A. if A then B."],
    ["if A then B. A."],
    ["The patient has fever and no fever."],
    ["""def transfer(amount, balance):
    assert amount > 0
    assert amount <= balance
    return balance - amount"""],
]


# ── App Layout ───────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Satisfaction Suffices",
    theme=gr.themes.Base(primary_hue="violet"),
    css="""
    .main-header { text-align: center; margin-bottom: 8px; }
    .main-header h1 { color: #c084fc; font-size: 2em; }
    .sub { text-align: center; color: #8b949e; margin-bottom: 16px; }
    .uniview-label { color: #c084fc; font-size: 13px; font-family: monospace; margin-bottom: 4px; }
    """,
) as demo:
    gr.HTML("""
    <div class="main-header">
        <h1>Satisfaction Suffices</h1>
    </div>
    <p class="sub">
        SAT-Gated Structural Containment for Frontier AI<br/>
        <em>A preference can be routed around. A structure cannot.</em>
    </p>
    """)

    # ── Universal Input (shared across all tabs) ────────────────────────
    gr.HTML('<p class="uniview-label">UNIVERSAL INPUT &mdash; same content, every tab is a different lens</p>')
    universal_input = gr.Textbox(
        value=DEFAULT_STATEMENT,
        lines=5,
        placeholder="Enter any text, code, or logical statement...",
        show_label=False,
        elem_id="universal-input",
    )
    gr.Examples(examples=EXAMPLES_UNIVERSAL, inputs=[universal_input], label="Quick load")

    with gr.Tabs():

        # ── Tab 1: Verify ───────────────────────────────────────────────
        with gr.TabItem("Verify"):
            gr.Markdown("**Lens:** Structural verification gate. Four verdicts: Verified, Contradiction, Paradox, Timeout.")
            with gr.Row():
                domain_input = gr.Dropdown(choices=DOMAIN_CHOICES, value="logic", label="Domain", scale=1)
                verify_btn = gr.Button("Verify", variant="primary", scale=1)
            verify_output = gr.HTML(label="Result")
            verify_btn.click(fn=run_verify, inputs=[universal_input, domain_input], outputs=verify_output)

        # ── Tab 2: Proof Evolution ──────────────────────────────────────
        with gr.TabItem("Proof Evolution"):
            gr.Markdown("**Lens:** Evolutionary search. Mutates the statement across generations to resolve contradictions.")
            with gr.Row():
                max_gens_input = gr.Slider(minimum=1, maximum=50, value=5, step=1, label="Max Generations", scale=2)
                evolve_btn = gr.Button("Evolve", variant="primary", scale=1)
            evolve_output = gr.HTML(label="Result")
            evolve_btn.click(fn=run_evolve, inputs=[universal_input, max_gens_input], outputs=evolve_output)

        # ── Tab 3: Search Tree ──────────────────────────────────────────
        with gr.TabItem("Search Tree"):
            gr.Markdown("**Lens:** Full evolution tree visualization. Hover nodes for details. White ring = best node.")
            with gr.Row():
                tree_gens = gr.Slider(minimum=1, maximum=30, value=5, step=1, label="Max Generations", scale=2)
                tree_pop = gr.Slider(minimum=2, maximum=16, value=6, step=1, label="Population Size", scale=2)
                tree_btn = gr.Button("Evolve & Visualize", variant="primary", scale=1)
            tree_output = gr.HTML(label="Evolution Tree")
            tree_btn.click(fn=run_tree_viz, inputs=[universal_input, tree_gens, tree_pop], outputs=tree_output)

        # ── Tab 4: Block Composer ───────────────────────────────────────
        with gr.TabItem("Block Composer"):
            gr.Markdown("**Lens:** No-code proof discovery. Snap logic blocks together. Composed result updates the universal input.")

            b1, v1a, v1b, v1c = make_logic_block_row(1, LOGIC_BLOCKS)
            b2, v2a, v2b, v2c = make_logic_block_row(2, LOGIC_BLOCKS)
            b3, v3a, v3b, v3c = make_logic_block_row(3, LOGIC_BLOCKS)
            b4, v4a, v4b, v4c = make_logic_block_row(4, LOGIC_BLOCKS)

            with gr.Row():
                compose_verify_btn = gr.Button("Compose & Verify", variant="primary")
                compose_evolve_btn = gr.Button("Compose & Evolve", variant="secondary")
                evolve_gens = gr.Slider(minimum=1, maximum=50, value=5, step=1, label="Generations")

            composed_output = gr.Code(label="Composed Proposition", language=None, interactive=False)
            composer_result = gr.HTML(label="Result")

            all_block_inputs = [b1, v1a, v1b, v1c, b2, v2a, v2b, v2c, b3, v3a, v3b, v3c, b4, v4a, v4b, v4c]

            compose_verify_btn.click(
                fn=compose_and_verify,
                inputs=all_block_inputs,
                outputs=[composed_output, composer_result, universal_input],
            )
            compose_evolve_btn.click(
                fn=compose_and_evolve,
                inputs=all_block_inputs + [evolve_gens],
                outputs=[composed_output, composer_result, universal_input],
            )

        # ── Tab 5: Program Discovery ────────────────────────────────────
        with gr.TabItem("Program Discovery"):
            gr.Markdown("**Lens:** No-code program discovery. Code patterns + meta-clauses compose into verifiable programs. Result updates universal input.")

            gr.Markdown("#### Code Patterns")
            cp1, cp1a, cp1b = make_pattern_row(1, CODE_PATTERN_BLOCKS, "Pattern")
            cp2, cp2a, cp2b = make_pattern_row(2, CODE_PATTERN_BLOCKS, "Pattern")
            cp3, cp3a, cp3b = make_pattern_row(3, CODE_PATTERN_BLOCKS, "Pattern")

            gr.Markdown("#### Meta-Clauses")
            mc1, mc1a, mc1b = make_pattern_row(1, META_CLAUSE_BLOCKS, "Meta-Clause")
            mc2, mc2a, mc2b = make_pattern_row(2, META_CLAUSE_BLOCKS, "Meta-Clause")
            mc3, mc3a, mc3b = make_pattern_row(3, META_CLAUSE_BLOCKS, "Meta-Clause")

            prog_verify_btn = gr.Button("Compose & Verify Program", variant="primary")
            prog_output = gr.Code(label="Composed Program", language="python", interactive=False)
            prog_result = gr.HTML(label="Result")

            prog_verify_btn.click(
                fn=compose_program,
                inputs=[cp1, cp1a, cp1b, cp2, cp2a, cp2b, cp3, cp3a, cp3b,
                        mc1, mc1a, mc1b, mc2, mc2a, mc2b, mc3, mc3a, mc3b],
                outputs=[prog_output, prog_result, universal_input],
            )

    gr.Markdown("""
    ---
    **[Paper](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.md)** |
    **[GitHub](https://github.com/TimeLordRaps/satisfaction-suffices)** |
    **[PyPI](https://pypi.org/project/satisfaction-suffices/)** |
<<<<<<< Updated upstream
    **License: [The Time License v7.2](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE)**
=======
    **License: [The Time License](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE)**
>>>>>>> Stashed changes

    *The SAT solver does not have preferences. It has proofs.*
    """)

demo.launch()
