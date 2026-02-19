# OHDSIAssistant (R) - ACP Client

This package provides a thin R client for the ACP study agent. It assumes the ACP server is already running and accessible over HTTP.

## Quick Start

```r
devtools::load_all("R/OHDSIAssistant")
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")
```

## Phenotype Recommendations (ACP Flow)

File-based study intent:

```r
rec <- OHDSIAssistant::suggestPhenotypes(
  protocolPath = "demo/protocol.md",
  maxResults = 10,
  candidateLimit = 10,
  interactive = TRUE
)
```

Direct study intent:

```r
rec <- OHDSIAssistant::suggestPhenotypes(
  studyIntent = "Identify clinical risk factors for older adults with GI bleeding in hospital settings.",
  maxResults = 10
)
```

Interactive prompt (if no intent provided):

```r
rec <- OHDSIAssistant::suggestPhenotypes()
```

## Notes

- The ACP server must be running and configured with its MCP connection.
- The R client calls ACP `/flows/phenotype_recommendation`.
- The response includes `recommendations`, which contains the validated core output.
