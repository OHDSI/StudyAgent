Return JSON that matches the output schema.
- Set status to "ok" when the study intent clearly supports all three cohort statements.
- Set status to "needs_clarification" when the target, comparator, outcome, or comparison framing is underspecified.
- Provide a short plan for how you derived the cohort statements.
- Provide a concise target cohort statement (index cohort) based on the study intent.
- Provide a concise comparator cohort statement (comparison cohort) based on the study intent.
- Provide a concise outcome cohort statement (event cohort) based on the study intent.
- Provide one or more concise outcome cohort statements in outcome_statements based on the study intent.
- Set outcome_statement to the first or primary outcome statement for compatibility.
- Include a brief rationale that connects the statements to the study intent.
- Include 1-3 clarifying questions when status is "needs_clarification".

Use this guidance for the statements:
- Target cohort: "If you were designing an observational retrospective study with the following study intent,
  what would be the target cohort for the study? In other words, the subset of the sampling frame for which
  you would define an index date which would be distinct from the outcome cohort, which would be the persons
  who had the event of interest."
- Comparator cohort: "If you were designing an observational retrospective cohort method study with the following
  study intent, what would be the comparator cohort for the study? In other words, the subset of the sampling frame
  for which you would define an index date for an alternative exposure or reference group to compare against the
  target cohort."
- Outcome cohort: "If you were designing an observational retrospective study with the following study intent,
  what would be the outcome cohort for the study? In other words, the subset of the sampling frame for which
  you would define an event of interest that would likely occur after the index date for persons in a target
  or comparator cohort."
