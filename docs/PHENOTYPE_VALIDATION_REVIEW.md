**Phenotype Validation Review (Keeper + ACP + MCP)**

This service integrates Keeper-style patient summaries with ACP/MCP orchestration while enforcing strict PHI/PII controls. The LLM never sees raw patient identifiers or dates.

**Flow Summary**
1. ACP receives a single Keeper row (`keeper_row`) or a path to one row.
2. ACP calls MCP `keeper_sanitize_row` to remove PHI/PII (fail-closed if sanitized output still contains PHI patterns).
3. MCP builds a de-identified patient summary prompt.
4. ACP calls the LLM with sanitized content only.
5. MCP parses the LLM output into `yes | no | unknown`.

**PHI/PII Rules (HIPAA 18)**
The sanitizer removes or redacts:
1. Names
2. Geographic subdivisions smaller than state
3. All elements of dates (except year); ages > 89 are bucketed
4. Phone/fax numbers
5. Email addresses
6. Social Security numbers
7. Medical record numbers
8. Health plan beneficiary numbers
9. Account numbers
10. Certificate/license numbers
11. Vehicle identifiers
12. Device identifiers
13. URLs
14. IP addresses
15. Biometric identifiers
16. Full face images and comparable images
17. Any other unique identifying number or code (except investigator-assigned codes)

**Age Handling**
- Ages are bucketed into 5-year bins.
- Ages ≥ 85 are bucketed as `85+`.

**Temporal Handling**
- Dates are removed or redacted.
- Relative timing is collapsed into prior/during/after phrasing.

**Output**
The LLM must return:
```json
{
  "label": "yes|no|unknown",
  "rationale": "..."
}
```

**Notes**
- The service only accepts one patient at a time.
- Any PHI detected after sanitization causes a fail-closed error.
