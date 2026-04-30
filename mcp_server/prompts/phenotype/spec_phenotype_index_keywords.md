Output contract:
{
  "retrieval_keywords": ["string"]
}

### HEURISTICS/RULES
For `phenotype_index_keywords`
- Return 6 to 12 short keyword phrases unless the phenotype metadata is too sparse.
- Prefer disease, syndrome, clinical focus, population, setting, code-family, and methodology cues.
- Each keyword should usually be 1 to 4 words. Acronyms are allowed.
- Avoid stop words, generic filler, and full-sentence fragments.
- Do not invent unsupported facts.
- Use supplied source metadata, concept labels, and methodology cues when helpful.

Constraints:
- JSON only; no markdown/fences.
- Keep output compact.
