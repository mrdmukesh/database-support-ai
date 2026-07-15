from evaluation.reporting.comparison import comparison_report


def test_comparison_report_groups_and_detects_regressions():
    baseline = [{"domain":"banking","category":"retry_failure","difficulty":"hard","release":"1","model_version":"m1","judge_version":"j1","weighted_score":90,"confidence":.9,"cost_usd":.01,"duration_seconds":10}]
    candidate = [{"domain":"banking","category":"retry_failure","difficulty":"hard","release":"2","model_version":"m2","judge_version":"j1","weighted_score":70,"confidence":.7,"cost_usd":.02,"duration_seconds":12}]
    report = comparison_report(baseline, candidate)
    assert report["by_dimension"]["domain"]["banking"]["score_delta"] == -20
    assert report["regressions"]
    assert report["top_failures"][0]["weighted_score"] == 70
