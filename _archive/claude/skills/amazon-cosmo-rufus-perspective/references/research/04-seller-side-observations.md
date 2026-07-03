# 04 Seller-Side Observations

## Boundary

This file contains seller-side inference from public sources and operational patterns. It is not an official Amazon ranking factor list and must not be presented as such.

## Common Failure Patterns

### Keyword Present But Relationship Missing

The Listing contains the phrase, but it does not explain the buyer state or use context. Example: "filterless" appears, but the page does not connect it to "no replacement cost", "low maintenance", or "pet owner convenience".

### CTR Good, CVR Weak

The query-product relationship gets enough attention, but detail-page evidence does not resolve objections. Likely Rufus-style questions remain unanswered.

### Impressions High, CTR Weak

The product is being exposed to a broad or wrong semantic neighborhood. This may be keyword mismatch, weak main image, or poor category identity.

### ACOS High Despite Orders

The semantic promise may be correct, but price/trust/review support is too weak relative to competitive alternatives.

### Review Contradiction

The Listing claims a benefit that reviews undermine or do not support. A conversational assistant would surface the contradiction.

## Practical Diagnosis Questions

- What buyer question does this keyword represent?
- What relationship does the platform need to infer?
- Which page element proves that relationship?
- What would Rufus answer if asked "is this good for my situation?"
- Which ad metric validates or falsifies the hypothesis?

