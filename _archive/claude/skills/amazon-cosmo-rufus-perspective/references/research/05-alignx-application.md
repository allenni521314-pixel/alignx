# 05 AlignX Application

## Core Loop

```text
ASIN selection
-> Listing diagnosis
-> COSMO/Rufus hypothesis
-> Listing action
-> ad validation
-> feedback round
-> learning memory
-> next round
```

## COSMO/Rufus Hypothesis Format

Each diagnosis must become a hypothesis:

```json
{
  "hypothesis_id": "hypothesis-1",
  "cosmo_relation": "used_for | used_in | used_with | capable_of | is_a",
  "rufus_question": "Can this product answer the buyer's concrete question?",
  "listing_action": "What content change will make the relationship explicit?",
  "ad_keywords": ["query to validate"],
  "success_metrics": ["CTR", "CVR", "ACOS", "search_term_precision"],
  "failure_reason": "sample_not_enough | keyword_mismatch | image_click_gap | detail_trust_gap | price_promise_gap"
}
```

## Diagnosis Dimensions

1. Product identity: what is it?
2. Buyer state: what problem or desire triggered search?
3. Scenario: where/when is it used?
4. Relationship: used for / used in / used with / used on / capable of.
5. Evidence: title, bullets, images, A+, reviews, Q&A.
6. Risk: what objection blocks trust?
7. Validation: which ad group proves or falsifies this?

## AlignX Scoring Heuristic

- 0-20: identity and category clarity.
- 0-20: buyer state/pain clarity.
- 0-20: relationship graph completeness.
- 0-20: evidence and objection handling.
- 0-20: validation readiness.

## Output Discipline

Do not say "Amazon will rank this higher." Say:

- "This improves platform-understanding readiness."
- "This reduces query-product ambiguity."
- "This creates a testable advertising hypothesis."
- "This should be validated by CTR/CVR/ACOS before being treated as learning."

