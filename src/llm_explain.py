"""
llm_explain.py

Takes the computed estimate and similar ticket evidence, then generates
a readable explanation. Works in two modes:

1. Template mode (default): Generates explanation from a structured template.
   No API key needed. Always works.

2. LLM mode (optional): If OPENAI_API_KEY is set in .env, uses OpenAI to
   generate a richer explanation with reasoning and missing-info suggestions.

The LLM does NOT calculate estimates — it only explains estimates that were
already computed by estimate_ticket.py. The code calculates, the LLM explains.
"""

import os
from config import OPENAI_API_KEY
from estimate_ticket import estimate_ticket, build_combined_text

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def generate_explanation(ticket_info, estimate_result, use_llm=False):
    """
    Generate a human-readable explanation of the estimate.

    Args:
        ticket_info: dict with summary, issue_type, description, etc.
        estimate_result: dict from estimate_ticket() with predictions and similar tickets
        use_llm: If True and OPENAI_API_KEY is set, use OpenAI for richer explanation

    Returns:
        Formatted explanation string
    """
    if use_llm and ANTHROPIC_API_KEY:
        return _llm_explanation(ticket_info, estimate_result)
    else:
        return _template_explanation(ticket_info, estimate_result)


def _template_explanation(ticket_info, estimate_result):
    """Generate explanation from a structured template (no API needed)."""
    lines = []

    summary = ticket_info.get("summary", "Unknown")
    issue_type = ticket_info.get("issue_type", "Unknown")
    lines.append(f'New ticket: "{summary}"')
    lines.append(f"Issue type: {issue_type}")
    lines.append("")

    # Estimates
    sp = estimate_result["suggested_story_points"]
    ct_low = estimate_result["cycle_time_low"]
    ct_high = estimate_result["cycle_time_high"]
    confidence = estimate_result["confidence"]

    if sp is not None:
        lines.append(f"Suggested story points: {sp:.0f}")
    else:
        lines.append("Suggested story points: N/A (insufficient similar tickets)")

    if ct_low is not None:
        lines.append(f"Estimated cycle time: {ct_low}–{ct_high} working days")
    else:
        lines.append("Estimated cycle time: N/A (insufficient similar tickets)")

    lines.append(f"Confidence: {confidence}")
    lines.append("")

    # Reasoning
    similar = estimate_result["similar_tickets"]
    if similar:
        sp_values = [t["story_points"] for t in similar if t["story_points"] is not None]
        ct_values = [t["cycle_time_working_days"] for t in similar if t["cycle_time_working_days"] is not None]

        lines.append("Reason:")
        lines.append(f"  Based on {len(similar)} similar completed {issue_type} tickets.")
        if sp_values:
            lines.append(f"  Their story points ranged from {min(sp_values):.0f} to {max(sp_values):.0f}.")
        if ct_values:
            lines.append(f"  Their cycle times ranged from {min(ct_values)} to {max(ct_values)} working days.")

        avg_dist = sum(t["distance"] for t in similar) / len(similar)
        if avg_dist < 0.3:
            lines.append("  Similarity scores are high — these are close matches.")
        elif avg_dist < 0.5:
            lines.append("  Similarity scores are moderate — matches are reasonable but not exact.")
        else:
            lines.append("  Similarity scores are low — matches are weak.")
    else:
        lines.append("Reason:")
        lines.append(f"  No similar {issue_type} tickets found in the knowledge base.")
        lines.append("  The estimator cannot make a confident prediction.")

    lines.append("")

    # Similar tickets
    if similar:
        lines.append("Top similar tickets:")
        for i, t in enumerate(similar, 1):
            sp_str = f"{t['story_points']:.0f} SP" if t["story_points"] else "no SP"
            ct_str = f"{t['cycle_time_working_days']} working days" if t["cycle_time_working_days"] else "no CT"
            lines.append(f"  {i}. {t['issue_key']} — {sp_str} — {ct_str}")
        lines.append("")

    # Missing information
    lines.append("Missing information that would improve the estimate:")
    desc = ticket_info.get("description", "")
    if not desc or len(desc) < 50:
        lines.append("  - Ticket has a thin or missing description")
    if not ticket_info.get("components"):
        lines.append("  - No component specified")
    if not ticket_info.get("labels"):
        lines.append("  - No labels specified")
    if confidence == "Low":
        lines.append("  - Few similar tickets exist for this issue type")
    if not lines[-1].startswith("  -"):
        lines.append("  - None identified — ticket has good context")

    return "\n".join(lines)


def _llm_explanation(ticket_info, estimate_result):
    """Generate explanation using Anthropic Claude API (requires ANTHROPIC_API_KEY)."""
    try:
        import anthropic
    except ImportError:
        print("WARNING: anthropic package not installed. Falling back to template mode.")
        print("  Install with: pip install anthropic")
        return _template_explanation(ticket_info, estimate_result)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Build prompt with all computed data
    similar = estimate_result["similar_tickets"]
    similar_str = "\n".join(
        f"  - {t['issue_key']}: {t.get('story_points', 'N/A')} SP, "
        f"{t.get('cycle_time_working_days', 'N/A')} working days, "
        f"distance={t['distance']:.3f}"
        for t in similar
    )

    sp = estimate_result["suggested_story_points"]
    ct_low = estimate_result["cycle_time_low"]
    ct_high = estimate_result["cycle_time_high"]

    prompt = f"""You are a Jira estimation assistant. Based ONLY on the data below, write a short explanation of the estimate. Do NOT invent extra tickets or fake data.

New ticket:
  Summary: {ticket_info.get('summary', 'N/A')}
  Issue type: {ticket_info.get('issue_type', 'N/A')}
  Description: {(ticket_info.get('description', '') or '')[:500]}

Computed estimate:
  Suggested story points: {sp if sp else 'N/A'}
  Cycle time range: {f'{ct_low}-{ct_high} working days' if ct_low else 'N/A'}
  Confidence: {estimate_result['confidence']}

Similar historical tickets used:
{similar_str if similar_str else '  None found'}

Write your response in this format:
1. Suggested story points
2. Estimated cycle-time range
3. Confidence level
4. Short reasoning (2-3 sentences based on the similar tickets)
5. Top similar tickets (list them)
6. Missing information that would improve the estimate (bullet points)"""

    response = client.messages.create(
        model="bedrock.claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def estimate_and_explain(summary, issue_type, description=None, components=None,
                         labels=None, parent_summary=None, use_llm=False):
    """
    Full pipeline: estimate a ticket and generate an explanation.
    This is the main entry point for estimating a single new ticket.
    """
    ticket_info = {
        "summary": summary,
        "issue_type": issue_type,
        "description": description,
        "components": components,
        "labels": labels,
        "parent_summary": parent_summary,
    }

    result = estimate_ticket(
        summary=summary,
        issue_type=issue_type,
        description=description,
        components=components,
        labels=labels,
        parent_summary=parent_summary,
    )

    explanation = generate_explanation(ticket_info, result, use_llm=use_llm)
    return result, explanation


def main():
    """
    Interactive mode: estimate tickets from command line input.
    Loops until you type 'quit' or press Ctrl+C.
    No CSV needed — just type the ticket details.
    """
    print("=" * 60)
    print("JIRA TICKET ESTIMATOR")
    print("=" * 60)
    print()
    print("Type ticket details to get an estimate.")
    print("Type 'quit' or press Ctrl+C to exit.")
    print()

    while True:
        print("-" * 60)
        summary = input("\nSummary (required, or 'quit' to exit): ").strip()
        if not summary or summary.lower() == "quit":
            print("Goodbye.")
            break

        print("\nAvailable issue types: Tech, Story, Task, Bug, Sub-task")
        issue_type = input("Issue type (required): ").strip()
        if not issue_type:
            print("ERROR: Issue type is required. Try again.")
            continue

        description = input("Description (optional): ").strip() or None
        components_raw = input("Components (optional, comma-separated): ").strip()
        components = [c.strip() for c in components_raw.split(",") if c.strip()] or None
        labels_raw = input("Labels (optional, comma-separated): ").strip()
        labels = [l.strip() for l in labels_raw.split(",") if l.strip()] or None

        print("\nEstimating...")
        print()

        result, explanation = estimate_and_explain(
            summary=summary,
            issue_type=issue_type,
            description=description,
            components=components,
            labels=labels,
        )

        print(explanation)
        print()


if __name__ == "__main__":
    main()
