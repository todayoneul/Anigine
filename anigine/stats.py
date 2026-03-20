from __future__ import annotations
from dataclasses import replace
import cv2 as cv
import numpy as np
from .config import AnigineConfig, PRESETS
from .utils import _clamp, _odd_ksize

def compute_image_stats(image: np.ndarray) -> dict[str, float]:
    hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

    sat_mean = float(np.mean(hsv[:, :, 1]))
    val_std = float(np.std(hsv[:, :, 2]))
    gray_std = float(np.std(gray))

    edges = cv.Canny(gray, 80, 180)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)

    lap = cv.Laplacian(gray, cv.CV_32F)
    noise_level = float(np.std(lap))

    median5 = cv.medianBlur(gray, 5)
    abs_diff = cv.absdiff(gray, median5)
    speckle_ratio = float(np.mean(abs_diff > 12))

    dark_ratio = float(np.mean(gray < 55))
    bright_ratio = float(np.mean(gray > 220))

    return {
        "sat_mean": sat_mean,
        "val_std": val_std,
        "gray_std": gray_std,
        "edge_density": edge_density,
        "noise_level": noise_level,
        "speckle_ratio": speckle_ratio,
        "dark_ratio": dark_ratio,
        "bright_ratio": bright_ratio,
    }

def pick_auto_preset(image: np.ndarray) -> str:
    stats = compute_image_stats(image)
    edge_density = stats["edge_density"]
    noise_level = stats["noise_level"]
    speckle_ratio = stats["speckle_ratio"]
    sat_mean = stats["sat_mean"]
    gray_std = stats["gray_std"]
    dark_ratio = stats["dark_ratio"]

    if edge_density > 0.145 and gray_std > 48:
        return "ink"
    if sat_mean > 120 and edge_density < 0.02:
        return "color-pop"
    if sat_mean > 105 and speckle_ratio > 0.09:
        return "color-pop"
    if noise_level > 32 or dark_ratio > 0.35 or speckle_ratio > 0.07:
        return "soft"
    if sat_mean > 135 and edge_density < 0.11:
        return "color-pop"
    if sat_mean > 105:
        return "vibrant"
    return "classic"

def build_custom_auto_config(
    image: np.ndarray,
    dot_noise_strength: float,
) -> tuple[str, AnigineConfig, dict[str, float], dict[str, float]]:
    stats = compute_image_stats(image)
    base_name = pick_auto_preset(image)
    base_cfg = PRESETS[base_name]

    edge_density = stats["edge_density"]
    noise_level = stats["noise_level"]
    speckle_ratio = stats["speckle_ratio"]
    sat_mean = stats["sat_mean"]
    gray_std = stats["gray_std"]
    val_std = stats["val_std"]

    speckle_score = _clamp(speckle_ratio / 0.14, 0.0, 1.0)
    noise_score = _clamp(max(noise_level / 55.0, speckle_score), 0.0, 1.0)
    detail_score_raw = _clamp(edge_density / 0.18, 0.0, 1.0)
    detail_score = _clamp(detail_score_raw * (1.0 - 0.35 * speckle_score), 0.0, 1.0)
    contrast_score = _clamp(gray_std / 70.0, 0.0, 1.0)
    brightness_var_score = _clamp(val_std / 70.0, 0.0, 1.0)
    color_low_score = _clamp((130.0 - sat_mean) / 130.0, 0.0, 1.0)
    score = {
        "noise_score": noise_score,
        "speckle_score": speckle_score,
        "detail_score": detail_score,
        "contrast_score": contrast_score,
        "brightness_var_score": brightness_var_score,
        "color_low_score": color_low_score,
    }

    median_ksize = _odd_ksize(int(3 + 2 * round(noise_score * 2)))
    bilateral_passes = int(_clamp(round(1 + noise_score * 2), 1, 3))
    bilateral_sigma_color = int(_clamp(55 + noise_score * 55 + detail_score * 10, 45, 130))
    bilateral_sigma_space = int(_clamp(50 + noise_score * 40, 40, 120))

    block_size = _odd_ksize(int(7 + round(noise_score * 2) * 2), minimum=5)
    edge_c = int(_clamp(round(1 + noise_score * 2), 1, 5))

    canny_low = int(_clamp(38 + contrast_score * 55 + noise_score * 18, 25, 150))
    canny_high = int(_clamp(canny_low * (2.0 + 0.35 * brightness_var_score), canny_low + 25, 245))

    edge_open_iter = int(_clamp(round(1 + noise_score * dot_noise_strength), 0, 4))
    edge_close_iter = int(_clamp(round(1 + detail_score + 0.5 * dot_noise_strength), 1, 5))
    min_dot_area = int(_clamp(round(12 + 18 * noise_score * dot_noise_strength), 6, 220))

    if base_name == "color-pop" and edge_density < 0.03:
        bilateral_passes = max(bilateral_passes, 2)
        median_ksize = max(median_ksize, 5)
        min_dot_area = min(220, min_dot_area + 8)

    saturation_boost = _clamp(1.02 + 0.30 * color_low_score + 0.06 * contrast_score, 0.95, 1.45)
    contrast_alpha = _clamp(1.01 + 0.16 * (1.0 - contrast_score) + 0.05 * brightness_var_score, 1.0, 1.24)
    contrast_beta = _clamp(-8.0 * (0.55 - contrast_score), -16.0, 8.0)

    edge_strength = _clamp(0.83 + 0.17 * detail_score - 0.07 * noise_score, 0.75, 1.0)
    unsharp_amount = _clamp(0.32 + 0.42 * detail_score - 0.18 * noise_score, 0.18, 0.75)

    cfg = replace(
        base_cfg,
        bilateral_passes=bilateral_passes,
        bilateral_sigma_color=bilateral_sigma_color,
        bilateral_sigma_space=bilateral_sigma_space,
        median_ksize=median_ksize,
        edge_block_size=block_size,
        edge_c=edge_c,
        canny_low=canny_low,
        canny_high=canny_high,
        edge_open_iter=edge_open_iter,
        edge_close_iter=edge_close_iter,
        min_dot_area=min_dot_area,
        saturation_boost=float(saturation_boost),
        contrast_alpha=float(contrast_alpha),
        contrast_beta=float(contrast_beta),
        edge_strength=float(edge_strength),
        unsharp_amount=float(unsharp_amount),
    )

    return base_name, cfg, stats, score

def explain_processing_reason(base_name: str, stats: dict[str, float], score: dict[str, float]) -> str:
    parts: list[str] = [f"기본 스타일은 '{base_name}'을 시작점으로 사용"]
    if score["speckle_score"] >= 0.55:
        parts.append("미세 점(텍스처) 노이즈 지표가 높아 점 노이즈 억제를 강화")
    if score["noise_score"] >= 0.55:
        parts.append("노이즈 지표가 높아 스무딩/점 노이즈 제거를 강화")
    elif score["noise_score"] <= 0.25:
        parts.append("노이즈 지표가 낮아 디테일 보존 쪽으로 설정")
    if score["detail_score"] >= 0.6:
        parts.append("에지 밀도가 높아 윤곽선 강도를 높임")
    if score["contrast_score"] <= 0.35:
        parts.append("명암 대비가 낮아 contrast 보정을 강화")
    if stats["sat_mean"] < 95:
        parts.append("채도가 낮아 saturation boost를 증가")
    parts.append("Adaptive Threshold + Canny 결합 에지와 형태학 후처리를 적용")
    return "; ".join(parts)
