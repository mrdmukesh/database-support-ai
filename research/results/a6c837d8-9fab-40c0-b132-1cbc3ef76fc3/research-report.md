# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 1 scenario(s); 1 completed operationally. Deterministic pass rate: 0.0%. AI Judge mean: 0.0.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

shipping

## Scenario distribution

Domains: {'shipping': 1}. Difficulties: {'medium': 1}.

## Accuracy and quality

Operational completion: 100.0%. Overall accuracy: 0.0%. Deterministic pass rate: 0.0%. Domain scores: {'shipping': 0.0}. Difficulty scores: {'medium': 0.0}.

## Latency, tokens, and cost

Mean latency: 3.7353582000032475 s; median: 3.7353582000032475 s; tokens: 22393; estimated Judge cost: $0.000000.

## Failure categories

{"fail": 1}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

1 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: a6c837d8-9fab-40c0-b132-1cbc3ef76fc3; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.