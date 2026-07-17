# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 1 scenario(s); 1 completed operationally. Deterministic pass rate: 100.0%. AI Judge mean: 72.55.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

orders

## Scenario distribution

Domains: {'orders': 1}. Difficulties: {'medium': 1}.

## Accuracy and quality

Operational completion: 100.0%. Overall accuracy: 100.0%. Deterministic pass rate: 100.0%. Domain scores: {'orders': 72.55}. Difficulty scores: {'medium': 72.55}.

## Latency, tokens, and cost

Mean latency: 22.36666339999647 s; median: 22.36666339999647 s; tokens: 22098; estimated Judge cost: $0.000000.

## Failure categories

{"none": 1}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

0 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: b05c8189-b5c2-45d5-b7fa-ca8310f17c64; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.