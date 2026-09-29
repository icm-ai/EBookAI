# Runtime ablation pilots

This directory contains reviewed-gold experiment specifications whose purpose
is to challenge runtime complexity.

`runtime-occam-v1.json` compares:

```text
A  PyMuPDF + reconstruction
B  A + quality-aware routing
C  B + deterministic repair
D  C + source-grounded AI repair
```

The experiment is deliberately blocked until the selected real pages have
sufficient independently reviewed gold and consensus provenance.

Do not change the sample or evidence thresholds after seeing experiment results
without treating that change as a new governed experiment revision.
