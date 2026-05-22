# AlignXAMZ System Refactor Guide - Vector Foundation

## Goal
Refactor AlignXAMZ into a dynamic semantic-vector probability alignment system based on embedding space and cosine similarity.

## Semantic Vector Foundation
- Category mean anchor: convert the top 50 BSR ASIN listing texts into high-dimensional vectors and use mean pooling as the category-space anchor.
- COSMO 15 relation vectors: project Amazon COSMO's 15 canonical relations into the same vector space.
- Target listing vector: map the target ASIN or listing text into the same vector space and calculate cosine similarity against category and COSMO anchors.

## Core Modules
- Backend: introduce a distance-computation module behind the COSMO/intent analysis flow.
- Frontend: do not expose vector foundation mechanics. Pages should show only business conclusions, scores, and recommendations produced by the backend.

## Strict Limits
- Do not rewrite existing frontend UI structures for unrelated cleanup.
- Keep the existing prompt-track logic intact.
- Dual-track validation is mandatory: prompt-rule track and semantic-vector track must both be returned.
- Activate vector-derived labels only when confidence is greater than `0.85`; otherwise fall back to the prompt track.

## Required Checks
- Run `npm run lint`.
- Run `npm run build`.
