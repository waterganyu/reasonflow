"""Email drafter — turn bullet points into a polished email, then review it.

This shows:
- Two-stage LLM pipeline (draft → review)
- LLMNode chaining where the second LLM critiques the first
- Saving the final output to file

Run with:
    reasonflow run examples/email_drafter.py -v recipient="Engineering Team" -v subject="Q1 Results"
"""

from datetime import datetime
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def prepare_input(state):
    """Prepare the email context from bullet points."""
    bullets = state.get("bullets", [
        "Q1 revenue up 23% YoY",
        "Shipped 3 major features: real-time collab, API v2, mobile app",
        "Customer churn dropped from 5.2% to 3.8%",
        "Hired 12 new engineers, 4 still in pipeline",
        "Infrastructure costs reduced 15% via migration to ARM instances",
        "Next quarter focus: enterprise tier launch and SOC2 certification",
    ])

    return {
        "bullets": bullets,
        "recipient": state.get("recipient", "Team"),
        "subject": state.get("subject", "Update"),
        "tone": state.get("tone", "professional but warm"),
    }


@LLMNode(model="claude-haiku", budget="$0.05")
def draft_email(state):
    """You are a professional email writer. Draft an email from these bullet points.

    To: {recipient}
    Subject: {subject}
    Tone: {tone}

    Key points:
    {bullets}

    Write a well-structured email that:
    - Opens with a brief greeting
    - Covers all bullet points naturally (don't just list them)
    - Closes with a forward-looking statement
    - Keeps it under 250 words

    Return as JSON with keys: "subject_line", "body", "word_count".
    """
    pass


@LLMNode(model="claude-sonnet", budget="$0.08")
def review_email(state):
    """You are an executive communications coach. Review this draft email.

    Subject: {subject_line}

    {body}

    Evaluate on:
    1. Clarity and conciseness
    2. Tone appropriateness
    3. Missing information or unclear points
    4. Grammar and style

    If improvements are needed, provide a revised version.
    Return as JSON with keys:
    - "score" (1-10)
    - "feedback" (list of specific suggestions)
    - "revised_body" (improved version, or null if the draft is good)
    """
    pass


@CodeNode
def save_draft(state):
    """Save the final email draft to a file."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    draft_dir = Path.home() / ".reasonflow" / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    draft_path = draft_dir / f"email_{timestamp}.txt"

    body = state.get("revised_body") or state.get("body", "")
    subject = state.get("subject_line", state.get("subject", ""))

    content = f"Subject: {subject}\nTo: {state.get('recipient', '')}\n\n{body}\n"
    draft_path.write_text(content)

    return {
        "final_body": body,
        "draft_path": str(draft_path),
        "was_revised": state.get("revised_body") is not None,
    }


# ── Build the DAG ───────────────────────────────────────

dag = DAG("email-drafter", budget="$0.20", debug=True)

dag.connect(prepare_input >> draft_email >> review_email >> save_draft)


if __name__ == "__main__":
    result = dag.run()
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Subject: {result.state.get('subject_line', '')}")
        print(f"Score: {result.state.get('score', '?')}/10")
        if result.state.get("was_revised"):
            print("(Email was revised based on review)")
        print(f"\n{result.state.get('final_body', '')}")
        print(f"\nFeedback:")
        for fb in result.state.get("feedback", []):
            print(f"  - {fb}")
        print(f"\nSaved to: {result.state.get('draft_path')}")
    else:
        print(f"Error: {result.error}")
