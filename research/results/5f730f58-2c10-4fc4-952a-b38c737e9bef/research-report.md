# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 1 scenario(s); 1 completed operationally. Deterministic pass rate: 100.0%. AI Judge mean: 81.45.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

banking

## Scenario distribution

Domains: {'banking': 1}. Difficulties: {'easy': 1}.

## Accuracy and quality

Operational completion: 100.0%. Overall accuracy: 100.0%. Deterministic pass rate: 100.0%. Domain scores: {'banking': 81.45}. Difficulty scores: {'easy': 81.45}.

## Latency, tokens, and cost

Mean latency: 28.9116611999998 s; median: 28.9116611999998 s; tokens: 23424; estimated Judge cost: $0.000000.

## Failure categories

{"none": 1}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

1 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: 5f730f58-2c10-4fc4-952a-b38c737e9bef; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.