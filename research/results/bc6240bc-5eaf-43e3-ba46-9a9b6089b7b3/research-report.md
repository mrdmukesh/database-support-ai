# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 124 scenario(s); 5 completed operationally. Deterministic pass rate: 0.0%. AI Judge mean: 0.0.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

banking, clinic, orders, payroll, shipping

## Scenario distribution

Domains: {'banking': 25, 'clinic': 25, 'orders': 25, 'payroll': 25, 'shipping': 24}. Difficulties: {'easy': 20, 'hard': 45, 'medium': 49, 'expert': 10}.

## Accuracy and quality

Operational completion: 4.0%. Overall accuracy: 0.0%. Deterministic pass rate: 0.0%. Domain scores: {'shipping': 0.0}. Difficulty scores: {'hard': 0.0, 'medium': 0.0}.

## Latency, tokens, and cost

Mean latency: 0.7055237846773913 s; median: 0.5541549500012479 s; tokens: 105600; estimated Judge cost: $0.000000.

## Failure categories

{"MySQL verification translator could not find the scenario condition": 99, "Scenario defect not reproducible": 20, "fail": 5}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

5 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: bc6240bc-5eaf-43e3-ba46-9a9b6089b7b3; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.