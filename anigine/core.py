from __future__ import annotations
import cv2 as cv
import numpy as np
from .config import AnigineConfig

def apply_intensity_transform(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    transformed = cv.convertScaleAbs(image, alpha=cfg.contrast_alpha, beta=cfg.contrast_beta)
    if not cfg.use_clahe:
        return transformed

    lab = cv.cvtColor(transformed, cv.COLOR_BGR2LAB)
    l, a, b = cv.split(lab)
    clahe = cv.createCLAHE(
        clipLimit=cfg.clahe_clip,
        tileGridSize=(cfg.clahe_grid, cfg.clahe_grid),
    )
    l = clahe.apply(l)
    return cv.cvtColor(cv.merge((l, a, b)), cv.COLOR_LAB2BGR)

def smooth_base(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    smoothed = image.copy()
    for _ in range(cfg.bilateral_passes):
        smoothed = cv.bilateralFilter(
            smoothed,
            d=cfg.bilateral_d,
            sigmaColor=cfg.bilateral_sigma_color,
            sigmaSpace=cfg.bilateral_sigma_space,
        )
    if cfg.median_ksize >= 3 and cfg.median_ksize % 2 == 1:
        smoothed = cv.medianBlur(smoothed, cfg.median_ksize)
    return smoothed

def quantize_colors(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    if cfg.color_bins <= 0:
        return image
    h, w = image.shape[:2]
    pixels = image.reshape((-1, 3)).astype(np.float32)
    total_pixels = pixels.shape[0]

    if total_pixels > cfg.kmeans_samples:
        indices = np.random.default_rng(42).choice(total_pixels, size=cfg.kmeans_samples, replace=False)
        train_data = pixels[indices]
    else:
        train_data = pixels

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 25, 0.2)
    _, _, centers = cv.kmeans(
        train_data,
        cfg.color_bins,
        None,
        criteria,
        cfg.kmeans_attempts,
        cv.KMEANS_PP_CENTERS,
    )

    diff = pixels[:, None, :] - centers[None, :, :]
    nearest = np.argmin(np.sum(diff * diff, axis=2), axis=1)
    quantized = centers[nearest].reshape((h, w, 3)).astype(np.uint8)
    return quantized

def remove_small_components(binary: np.ndarray, min_area: int) -> np.ndarray:
    if min_area <= 1:
        return binary
    num_labels, labels, stats, _ = cv.connectedComponentsWithStats(binary, connectivity=8)
    clean = np.zeros_like(binary)
    for label in range(1, num_labels):
        area = stats[label, cv.CC_STAT_AREA]
        if area >= min_area:
            clean[labels == label] = 255
    return clean

def detect_ink_edges(gray: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    blur = cv.GaussianBlur(gray, (5, 5), 1.1)
    blur = cv.bilateralFilter(blur, 5, 35, 35)
    blur = cv.medianBlur(blur, 3)

    block_size = cfg.edge_block_size if cfg.edge_block_size % 2 == 1 else cfg.edge_block_size + 1
    adaptive = cv.adaptiveThreshold(
        blur,
        255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        block_size,
        cfg.edge_c,
    )

    adaptive_edges = cv.bitwise_not(adaptive)
    canny_edges = cv.Canny(blur, cfg.canny_low, cfg.canny_high)
    edge_map = cv.bitwise_or(adaptive_edges, canny_edges)

    kernel = np.ones((3, 3), np.uint8)
    if cfg.edge_open_iter > 0:
        edge_map = cv.morphologyEx(edge_map, cv.MORPH_OPEN, kernel, iterations=cfg.edge_open_iter)
    if cfg.edge_close_iter > 0:
        edge_map = cv.morphologyEx(edge_map, cv.MORPH_CLOSE, kernel, iterations=cfg.edge_close_iter)

    edge_map = remove_small_components(edge_map, cfg.min_dot_area)

    if cfg.edge_dilate_iter > 0:
        edge_map = cv.dilate(edge_map, kernel, iterations=cfg.edge_dilate_iter)
    if cfg.edge_erode_iter > 0:
        edge_map = cv.erode(edge_map, kernel, iterations=cfg.edge_erode_iter)

    return cv.bitwise_not(edge_map)

def apply_unsharp(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    if cfg.unsharp_amount <= 0:
        return image
    blurred = cv.GaussianBlur(image, (0, 0), cfg.unsharp_sigma)
    return cv.addWeighted(image, 1 + cfg.unsharp_amount, blurred, -cfg.unsharp_amount, 0)

def boost_saturation(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * cfg.saturation_boost, 0, 255)
    return cv.cvtColor(hsv.astype(np.uint8), cv.COLOR_HSV2BGR)

def blend_edges(color_img: np.ndarray, edge_mask: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    edge_f = edge_mask.astype(np.float32) / 255.0
    edge_f = cfg.edge_strength * edge_f + (1.0 - cfg.edge_strength)
    edge_f = np.clip(edge_f, 0.0, 1.0)
    edge_f = edge_f[:, :, None]
    return np.clip(color_img.astype(np.float32) * edge_f, 0, 255).astype(np.uint8)

def apply_paper_grain(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    if cfg.paper_grain <= 0:
        return image
    noise = np.random.default_rng(1234).normal(0, 255 * cfg.paper_grain, image.shape).astype(np.float32)
    return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

def render_anigine(image: np.ndarray, cfg: AnigineConfig) -> np.ndarray:
    transformed = apply_intensity_transform(image, cfg)
    smoothed = smooth_base(transformed, cfg)
    quantized = quantize_colors(smoothed, cfg)
    saturated = boost_saturation(quantized, cfg)

    gray = cv.cvtColor(smoothed, cv.COLOR_BGR2GRAY)
    edges = detect_ink_edges(gray, cfg)
    inked = blend_edges(saturated, edges, cfg)
    sharpened = apply_unsharp(inked, cfg)
    return apply_paper_grain(sharpened, cfg)
