# 03 Search And Relevance Signals

## Source Priority

- Amazon Science: query-product semantic similarity.
- Amazon Science: implicit query parsing for product search.
- Amazon Science: graph-based multilingual product retrieval / graph-based multilingual language model.
- Amazon Science Shopping Queries Dataset / ESCI benchmark.
- Sell on Amazon official product listing guidance.

## Stable Public Concepts

Amazon search relevance research emphasizes:

- Query-product semantic similarity.
- Product relations and graph signals.
- Query parsing and intent structure.
- Essential / substitute / complement / irrelevant labels in the ESCI benchmark.
- Long-term customer trust depends on relevance quality.

## AlignX Translation

The working model should not be "keyword density". It should be:

```text
Query -> parsed intent -> product relationship graph -> evidence on detail page -> purchase feedback
```

## Four Relevance Tests

1. **Identity fit**: Is the product clearly the right object class?
2. **Intent fit**: Does it solve the exact buyer state, not just the broad category?
3. **Evidence fit**: Does the Listing prove the claim with title, bullets, images, A+, reviews, Q&A?
4. **Outcome fit**: Do click/order/ACOS data validate the relationship?

## Seller-Side Observable Implications

- Broad category terms can get impressions but weak conversion if intent fit is loose.
- Scenario and state-trigger terms often reveal more precise buyer motivation than pure attributes.
- Complementary relations matter for bundle, use case, and "used with" discovery.
- Search term reports should be interpreted as semantic feedback, not just bid optimization data.

