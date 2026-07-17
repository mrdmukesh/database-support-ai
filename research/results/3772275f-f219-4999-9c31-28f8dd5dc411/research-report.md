# LegacyDB Copilot AI Judge Evaluation Report

## Executive summary

This local-first run evaluated 125 scenario(s); 125 completed operationally. Deterministic pass rate: 0.0%. AI Judge mean: 1.7376.

## Methodology

Versioned scenarios were reset and injected into isolated local sqlserver databases, submitted through the local application API, deterministically validated, then independently assessed by the configured AI Judge.

## Databases and domains tested

banking, clinic, orders, payroll, shipping

## Scenario distribution

Domains: {'banking': 25, 'clinic': 25, 'orders': 25, 'payroll': 25, 'shipping': 25}. Difficulties: {'easy': 20, 'hard': 45, 'medium': 50, 'expert': 10}.

## Accuracy and quality

Operational completion: 100.0%. Overall accuracy: 0.0%. Deterministic pass rate: 0.0%. Domain scores: {'banking': 2.8960000000000004, 'clinic': 2.8960000000000004, 'orders': 0.0, 'payroll': 2.8960000000000004, 'shipping': 0.0}. Difficulty scores: {'easy': 0.0, 'expert': 0.0, 'hard': 4.826666666666667, 'medium': 0.0}.

## Latency, tokens, and cost

Mean latency: 1.9368245327999174 s; median: 2.022332999997161 s; tokens: 1484502; estimated Judge cost: $0.000000.

## Failure categories

{"fail": 125}

## False-positive and false-negative analysis

Requires human-labelled outcome classes beyond the current expected-answer rubric; no rates are asserted from insufficient evidence.

## Human review required

125 case(s) flagged. See scenario-level CSV.

## Limitations

This single-scenario quality gate does not support population-level conclusions. AI Judge scores are model-dependent.

## Reproducibility

Run ID: 3772275f-f219-4999-9c31-28f8dd5dc411; application version: 0.1.0; commit: 7fb451c1f3f8da1683ef503f4b3dca39290d75ec. Full configuration is stored in results.json with secrets excluded.