# 01 COSMO Knowledge Graph Research

## Source Priority

- Primary: Amazon Science publication, "COSMO: A large-scale e-commerce common sense knowledge generation and serving system at Amazon" (SIGMOD/PODS 2024).
- Primary PDF: Amazon Science COSMO paper.
- Adjacent primary: Amazon Science product-search relevance papers on query-product semantic similarity, implicit query parsing, graph-based multilingual retrieval.

## What COSMO Is

COSMO is Amazon's e-commerce commonsense knowledge generation and serving system. The public paper frames its core gap clearly: traditional e-commerce KGs capture concepts and product attributes, but often miss user intentions and commonsense relationships. COSMO mines user-centric commonsense knowledge from large-scale behavior data and uses LLM-generated seed assertions refined by classifiers and human annotation.

## Useful Public Claims

- COSMO expands e-commerce commonsense knowledge across 18 major Amazon categories.
- It uses instruction tuning to train COSMO-LM for faithful knowledge generation at scale.
- It has been deployed in Amazon search applications such as search navigation.
- Offline and online A/B experiments showed improvement.

## Relationship Types That Matter

From the COSMO paper and examples:

- `is_a`: product type/category identity.
- `used_for`: function or use case.
- `used_as`: role the product plays for a buyer.
- `used_on`: time, season, event, body part, surface, target object.
- `used_in`: location/facility/context.
- `used_with`: complementary product or bundle context.
- `capable_of`: capability/function.
- `causes_or_reduces`: inferred from buyer pain/state language, not a literal COSMO paper relation name.

## Operating Interpretation For AlignX

COSMO should be treated as a platform-understanding layer:

1. It tries to map query language to product commonsense relationships, not just match strings.
2. A Listing should make the product's category, use case, scenario, audience, pain state, and complementary relations explicit.
3. Missing relationships create ranking and recommendation ambiguity.
4. Over-claimed or unsupported relationships create trust/compliance risk.

## Seller-Side Observable Implications

These are inferred from public COSMO architecture plus search behavior, not official Amazon ranking weights:

- A product may fail even with keywords present if the surrounding relationship is missing.
- "Cat litter deodorizer" and "pet odor eliminator for home" can point to different intent graphs.
- Listing content must connect product identity to buyer state: "what it is" + "who uses it" + "where" + "for which pain" + "with what evidence".
- Advertising is a validation instrument: if a query brings clicks but not orders, the relationship may be recognized at query level but not trusted at product detail level.

