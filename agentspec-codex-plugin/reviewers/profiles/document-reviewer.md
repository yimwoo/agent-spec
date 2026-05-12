# Document Reviewer

The document reviewer checks generated or agent-authored DCRs, designs, source
candidates, discovery spikes, and workflow plans before they become lifecycle
authority.

Use the public `review-doc` entrypoint or the CLI fallback:

```bash
aspec review doc <path> --mode deterministic --json
aspec review doc <path> --verdict ready --reviewer human --summary "<summary>" --json
```

The review evidence belongs in `agent/doc-reviews/DOCREVIEW-*.yml`. Reviewer
rubrics and model-backed profiles are controller-selected; they are not exposed
as separate human commands.

