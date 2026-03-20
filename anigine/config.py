from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AnigineConfig:
    bilateral_passes: int = 2
    bilateral_d: int = 7
    bilateral_sigma_color: int = 80
    bilateral_sigma_space: int = 80
    median_ksize: int = 5
    use_clahe: bool = True
    clahe_clip: float = 2.0
    clahe_grid: int = 8
    color_bins: int = 16
    kmeans_samples: int = 50000
    kmeans_attempts: int = 3
    edge_block_size: int = 9
    edge_c: int = 2
    canny_low: int = 60
    canny_high: int = 140
    edge_dilate_iter: int = 1
    edge_erode_iter: int = 1
    edge_open_iter: int = 1
    edge_close_iter: int = 1
    min_dot_area: int = 18
    edge_strength: float = 0.95
    saturation_boost: float = 1.15
    contrast_alpha: float = 1.08
    contrast_beta: float = -5.0
    unsharp_amount: float = 0.5
    unsharp_sigma: float = 1.0
    paper_grain: float = 0.0

PRESETS: dict[str, AnigineConfig] = {
    "classic": AnigineConfig(),
    "vibrant": AnigineConfig(
        bilateral_passes=1,
        color_bins=14,
        saturation_boost=1.28,
        contrast_alpha=1.14,
        contrast_beta=-8,
        edge_strength=0.92,
        paper_grain=0.02,
    ),
    "color-pop": AnigineConfig(
        bilateral_passes=1,
        bilateral_d=5,
        bilateral_sigma_color=65,
        bilateral_sigma_space=65,
        median_ksize=3,
        color_bins=12,
        edge_block_size=7,
        edge_c=1,
        canny_low=70,
        canny_high=165,
        edge_strength=0.88,
        saturation_boost=1.42,
        contrast_alpha=1.18,
        contrast_beta=-6,
        unsharp_amount=0.62,
        unsharp_sigma=0.9,
    ),
    "ink": AnigineConfig(
        bilateral_passes=3,
        bilateral_sigma_color=100,
        color_bins=10,
        edge_block_size=11,
        edge_c=3,
        canny_low=45,
        canny_high=115,
        edge_dilate_iter=2,
        edge_erode_iter=1,
        edge_open_iter=1,
        edge_close_iter=2,
        min_dot_area=26,
        edge_strength=1.0,
        saturation_boost=0.95,
        contrast_alpha=1.0,
        contrast_beta=0,
    ),
    "soft": AnigineConfig(
        bilateral_passes=2,
        bilateral_d=9,
        bilateral_sigma_color=60,
        bilateral_sigma_space=60,
        median_ksize=7,
        color_bins=14,
        edge_block_size=7,
        edge_c=1,
        canny_low=70,
        canny_high=170,
        edge_open_iter=2,
        edge_close_iter=1,
        min_dot_area=30,
        edge_strength=0.85,
        saturation_boost=1.08,
        unsharp_amount=0.35,
    ),
    "faithful": AnigineConfig(
        bilateral_passes=1,
        bilateral_d=5,
        bilateral_sigma_color=40,
        bilateral_sigma_space=40,
        median_ksize=0,
        color_bins=0,
        use_clahe=False,
        saturation_boost=1.0,
        contrast_alpha=1.0,
        contrast_beta=0,
        edge_strength=0.9,
    ),
}
