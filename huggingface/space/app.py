"""
Satisfaction Suffices — Live Verification Demo
================================================
SAT-gated structural containment for AI.
Type any text, code, or logical statement — the gate returns one of four verdicts.
"""

import gradio as gr
from satisfaction_suffices import verify, evolve_proof, Verdict

DOMAIN_CHOICES = [
    "logic",
    "code",
    "math",
    "proof",
    "text",
    "med",
    "law",
    "bio",
    "cyber",
    "chem",
    "quantum",
    "philosophy",
]

VERDICT_COLORS = {
    Verdict.VERIFIED: "#22c55e",       # green
    Verdict.CONTRADICTION: "#ef4444",  # red
    Verdict.PARADOX: "#f59e0b",        # amber
    Verdict.TIMEOUT: "#6b7280",        # gray
}

VERDICT_EMOJI = {
    Verdict.VERIFIED: "VERIFIED",
    Verdict.CONTRADICTION: "CONTRADICTION",
    Verdict.PARADOX: "PARADOX",
    Verdict.TIMEOUT: "TIMEOUT",
}


def run_verify(content: str, domain: str) -> str:
    """Run verification and format the result as HTML."""
    if not content.strip():
        return "<p style='color: #6b7280;'>Enter content to verify.</p>"

    result = verify(content, domain=domain)

    color = VERDICT_COLORS[result.verdict]
    label = VERDICT_EMOJI[result.verdict]

    html = f"""
    <div style="font-family: monospace; padding: 16px; border: 2px solid {color}; border-radius: 8px; background: #0d1117;">
        <h2 style="color: {color}; margin: 0 0 12px 0;">{label}</h2>
        <table style="color: #c9d1d9; font-size: 14px; border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">SAT Ratio</td>
                <td style="padding: 4px 0;"><strong>{result.sat_ratio:.2%}</strong></td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Zone</td>
                <td style="padding: 4px 0;">{result.zone}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Constraints</td>
                <td style="padding: 4px 0;">{result.n_constraints} total</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Satisfied</td>
                <td style="padding: 4px 0;">{result.n_satisfied}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Refuted</td>
                <td style="padding: 4px 0;">{result.n_refuted}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Timeout</td>
                <td style="padding: 4px 0;">{result.n_timeout}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Paradox</td>
                <td style="padding: 4px 0;">{result.n_paradox}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Elapsed</td>
                <td style="padding: 4px 0;">{result.elapsed_ms:.1f} ms</td></tr>
        </table>
    </div>
    """
    return html


def run_evolve(content: str, max_gens: int) -> str:
    """Run proof evolution and format the result."""
    if not content.strip():
        return "<p style='color: #6b7280;'>Enter content to evolve.</p>"

    evo = evolve_proof(content, max_generations=int(max_gens))

    status_color = "#22c55e" if evo.resolved else "#ef4444"
    status_label = "RESOLVED" if evo.resolved else "UNRESOLVED"

    html = f"""
    <div style="font-family: monospace; padding: 16px; border: 2px solid {status_color}; border-radius: 8px; background: #0d1117;">
        <h2 style="color: {status_color}; margin: 0 0 12px 0;">{status_label}</h2>
        <table style="color: #c9d1d9; font-size: 14px; border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Best Status</td>
                <td style="padding: 4px 0;"><strong>{evo.best_node.status.name}</strong></td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Generations</td>
                <td style="padding: 4px 0;">{evo.generations_run}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Proved</td>
                <td style="padding: 4px 0;">{evo.proved_count}</td></tr>
            <tr><td style="padding: 4px 12px 4px 0; color: #8b949e;">Total Nodes</td>
                <td style="padding: 4px 0;">{evo.total_nodes}</td></tr>
        </table>
    </div>
    """
    return html


EXAMPLES_VERIFY = [
    ["if A then B. A.", "logic"],
    ["A. not A. if A then B.", "logic"],
    ["x + 2 = 5", "math"],
    ["""def transfer(amount, balance):
    assert amount > 0
    assert amount <= balance
    return balance - amount""", "code"],
    ["The patient has fever and no fever.", "med"],
    ["Energy is conserved. Energy is not conserved.", "text"],
]

EXAMPLES_EVOLVE = [
    ["A. not A.", 5],
    ["if A then B. if B then C. not C. A.", 10],
]

with gr.Blocks(
    title="Satisfaction Suffices",
    theme=gr.themes.Base(primary_hue="violet"),
    css="""
    .main-header { text-align: center; margin-bottom: 8px; }
    .main-header h1 { color: #c084fc; font-size: 2em; }
    .sub { text-align: center; color: #8b949e; margin-bottom: 24px; }
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

    with gr.Tabs():
        with gr.TabItem("Verify"):
            gr.Markdown("### Verification Gate\nPaste any text, code, or logical statement. The gate checks satisfiability and returns one of **four verdicts**: Verified, Contradiction, Paradox, or Timeout.")
            with gr.Row():
                with gr.Column():
                    content_input = gr.Textbox(
                        label="Content",
                        placeholder="if A then B. A.",
                        lines=6,
                    )
                    domain_input = gr.Dropdown(
                        choices=DOMAIN_CHOICES,
                        value="logic",
                        label="Domain",
                    )
                    verify_btn = gr.Button("Verify", variant="primary")
                with gr.Column():
                    verify_output = gr.HTML(label="Result")

            gr.Examples(
                examples=EXAMPLES_VERIFY,
                inputs=[content_input, domain_input],
                label="Try these",
            )

            verify_btn.click(
                fn=run_verify,
                inputs=[content_input, domain_input],
                outputs=verify_output,
            )

        with gr.TabItem("Proof Evolution"):
            gr.Markdown("### Proof Evolution\nGive a contradictory statement. The evolver mutates it across generations trying to resolve the contradiction.")
            with gr.Row():
                with gr.Column():
                    evolve_input = gr.Textbox(
                        label="Content",
                        placeholder="A. not A.",
                        lines=4,
                    )
                    max_gens_input = gr.Slider(
                        minimum=1,
                        maximum=50,
                        value=5,
                        step=1,
                        label="Max Generations",
                    )
                    evolve_btn = gr.Button("Evolve", variant="primary")
                with gr.Column():
                    evolve_output = gr.HTML(label="Result")

            gr.Examples(
                examples=EXAMPLES_EVOLVE,
                inputs=[evolve_input, max_gens_input],
                label="Try these",
            )

            evolve_btn.click(
                fn=run_evolve,
                inputs=[evolve_input, max_gens_input],
                outputs=evolve_output,
            )

    gr.Markdown("""
    ---
    **[Paper](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.md)** |
    **[GitHub](https://github.com/TimeLordRaps/satisfaction-suffices)** |
    **[PyPI](https://pypi.org/project/satisfaction-suffices/)** |
    **License: [CCUL v1.0](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE)**

    *The SAT solver does not have preferences. It has proofs.*
    """)

demo.launch()
