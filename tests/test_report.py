from __future__ import annotations

from seeingbench.benchmark.report import render_markdown_report


def test_markdown_report_renders_core_metrics() -> None:
    markdown = render_markdown_report(
        {
            "algorithm": "example",
            "image_similarity": {"mse": 0.1, "psnr_db": 10.0, "ssim_global": 0.5},
            "structural_accuracy": {"gradient_correlation": 0.2},
            "frequency_recovery": {
                "correlation_0_5_limit_fraction": 0.4,
                "diffraction_frequency_fraction_of_nyquist": 0.25,
                "correlation_0_5_limit_relative_to_diffraction": 1.6,
                "mean_correlation_beyond_diffraction": 0.1,
            },
            "false_detail": {
                "unsupported_energy_fraction": 0.3,
                "cutoff_fraction": 0.6,
            },
            "warp_recovery": None,
            "metadata": {"runtime_s": 1.0, "case_metadata": {"config": {"frame_count": 2}}},
        }
    )

    assert "# SeeingBench Report: example" in markdown
    assert "Unsupported high-frequency energy fraction" in markdown
