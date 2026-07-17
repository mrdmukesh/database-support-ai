# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 1 scenario(s); 1 completed operationally. Deterministic pass rate: 100.0%. AI Judge mean: 92.15.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

shipping

## Scenario distribution

Domains: {'shipping': 1}. Difficulties: {'medium': 1}.

## Accuracy and quality

Operational completion: 100.0%. Overall accuracy: 100.0%. Deterministic pass rate: 100.0%. Domain scores: {'shipping': 92.15}. Difficulty scores: {'medium': 92.15}.

## Latency, tokens, and cost

Mean latency: 27.575857499999984 s; median: 27.575857499999984 s; tokens: 32662; estimated Judge cost: $0.000000.

## Failure categories

{"none": 1}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

0 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: ef9a60c2-08f7-44f1-b3cc-2d50d300a5f5; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.