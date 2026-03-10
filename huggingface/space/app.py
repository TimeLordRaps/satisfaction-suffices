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
    ["""#include <mutex>
#include <shared_mutex>
#include <thread>
#include <queue>
#include <condition_variable>
#include <future>
#include <functional>
#include <atomic>

// Thread-safe async message client with lock hierarchy
class AsyncMessageClient {
    mutable std::shared_mutex registry_mutex_;   // Level 2: protects channel map
    mutable std::mutex queue_mutex_;              // Level 1: protects send queue
    std::condition_variable queue_cv_;
    std::atomic<bool> running_{true};
    std::queue<std::function<void()>> send_queue_;

    // Lock ordering invariant: always acquire registry_mutex_ before queue_mutex_
    // Violating this ordering causes deadlock.

    void send_worker() {
        while (running_.load(std::memory_order_acquire)) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> lock(queue_mutex_);
                queue_cv_.wait(lock, [this] {
                    return !send_queue_.empty() || !running_;
                });
                if (!running_ && send_queue_.empty()) return;
                task = std::move(send_queue_.front());
                send_queue_.pop();
            }
            task();  // execute outside lock
        }
    }

public:
    // Meta-clause: message text must satisfy ALL of:
    //   1. Non-empty (structural precondition)
    //   2. Length <= 4096 (bounded resource)  
    //   3. No null bytes (transport safety)
    //   4. UTF-8 valid (encoding invariant)
    std::future<bool> send(const std::string& channel, std::string message) {
        // Meta-clause enforcement: structural verification before enqueue
        assert(!message.empty());           // Clause 1: existence
        assert(message.size() <= 4096);     // Clause 2: bounded
        assert(message.find('\\0') == std::string::npos);  // Clause 3: transport
        // Clause 4: UTF-8 validity checked by gate

        auto promise = std::make_shared<std::promise<bool>>();
        auto future = promise->get_future();

        {
            std::shared_lock<std::shared_mutex> reg_lock(registry_mutex_);
            std::lock_guard<std::mutex> q_lock(queue_mutex_);
            send_queue_.push([promise, ch=channel, msg=std::move(message)] {
                // Actual send — promise fulfills on completion
                promise->set_value(true);
            });
        }
        queue_cv_.notify_one();
        return future;
    }

    void shutdown() {
        running_.store(false, std::memory_order_release);
        queue_cv_.notify_all();
    }
};""", "code"],
    ["""// Meta-clauses on message content:
// 1. Every message has a sender AND a recipient (completeness)
// 2. No message can be both encrypted AND plaintext (mutual exclusion)
// 3. If message is marked urgent, it must have a TTL (conditional dependency)
// 4. A message cannot be delivered AND undelivered simultaneously (consistency)

sender_exists AND recipient_exists.
encrypted AND plaintext.
urgent AND NOT has_ttl.
delivered AND NOT delivered.""", "logic"],
    ["if A then B. A.", "logic"],
    ["A. not A. if A then B.", "logic"],
    ["""def transfer(amount, balance):
    assert amount > 0
    assert amount <= balance
    return balance - amount""", "code"],
    ["The patient has fever and no fever.", "med"],
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
