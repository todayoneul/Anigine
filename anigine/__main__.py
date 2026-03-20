from __future__ import annotations
import argparse
from pathlib import Path
from dataclasses import replace
import cv2 as cv

from .config import AnigineConfig, PRESETS
from .utils import list_images, load_bgr, compose_compare, save_image, _clamp
from .stats import compute_image_stats, build_custom_auto_config, explain_processing_reason
from .core import render_anigine

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="High-quality OpenCV animation renderer (Anigine).")
    parser.add_argument("--input", "-i", required=True, help="Input image path or folder")
    parser.add_argument("--output", "-o", required=True, help="Output image path or folder")
    preset_choices = sorted(list(PRESETS.keys()) + ["auto"])
    parser.add_argument("--preset", default="classic", choices=preset_choices, help="Rendering preset")
    parser.add_argument("--recursive", action="store_true", help="Scan input folder recursively")
    parser.add_argument("--suffix", default="_anigine", help="Output filename suffix")
    parser.add_argument("--ext", default=".png", help="Output extension")
    parser.add_argument("--compare", action="store_true", help="Save side-by-side comparison")
    parser.add_argument("--show", action="store_true", help="Show preview windows")
    parser.add_argument("--max-side", type=int, default=1600, help="Resize large inputs")
    parser.add_argument("--dot-noise-suppression", type=float, default=1.0, help="Noise suppression strength (0.5~3.0)")
    return parser.parse_args()

def apply_dot_noise_strength(cfg: AnigineConfig, strength: float) -> AnigineConfig:
    strength = _clamp(strength, 0.5, 3.0)
    open_iter = int(_clamp(round(cfg.edge_open_iter * strength), 0, 4))
    close_iter = int(_clamp(round(cfg.edge_close_iter * (0.6 + 0.4 * strength)), 0, 5))
    min_area = int(_clamp(round(cfg.min_dot_area * strength), 4, 200))
    return replace(cfg, edge_open_iter=open_iter, edge_close_iter=close_iter, min_dot_area=min_area)

def write_batch_report(output_dir: Path, rows: list[dict[str, str]]) -> None:
    if not rows: return
    report_path = output_dir / "anigine_batch_report.md"
    lines = ["# Anigine 애니메이션 렌더링 리포트", "", f"총 이미지 수: {len(rows)}", ""]
    for idx, row in enumerate(rows, 1):
        lines.extend([
            f"## {idx}. {row['image']}",
            f"- 출력 파일: {row['output']}",
            f"- 베이스 프리셋: {row['base']}, 적용 프리셋: {row['applied']}",
            f"- 처리 근거: {row['reason']}",
            f"- 통계: sat_mean={row['sat_mean']}, edge_density={row['edge_density']}, noise={row['noise_level']}",
            ""
        ])
    report_path.write_text("\n".join(lines), encoding="utf-8")

def process_single(input_path: Path, output_path: Path, preset_name: str, compare: bool, show: bool, max_side: int, dot_noise_strength: float) -> None:
    source = load_bgr(input_path, max_side)
    if preset_name == "auto":
        base_name, cfg, _, _ = build_custom_auto_config(source, dot_noise_strength)
        applied = f"auto({base_name})"
    else:
        applied = preset_name
        cfg = apply_dot_noise_strength(PRESETS[preset_name], dot_noise_strength)
    
    print(f"Processing [{input_path.name}] with {applied}...")
    anigine_out = render_anigine(source, cfg)
    result = compose_compare(source, anigine_out) if compare else anigine_out
    save_image(output_path, result)
    
    if show:
        cv.imshow("source", source); cv.imshow("anigine", anigine_out)
        cv.waitKey(0); cv.destroyAllWindows()

def process_batch(input_dir: Path, output_dir: Path, preset_name: str, recursive: bool, suffix: str, ext: str, compare: bool, max_side: int, dot_noise_strength: float) -> None:
    images = list_images(input_dir, recursive)
    if not images: raise ValueError(f"No images in: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_rows = []
    for path in images:
        rel = path.relative_to(input_dir)
        out_path = output_dir / rel.parent / (rel.stem + suffix + ext)
        source = load_bgr(path, max_side)
        if preset_name == "auto":
            base_name, cfg, stats, score = build_custom_auto_config(source, dot_noise_strength)
            applied = f"auto({base_name})"
            reason = explain_processing_reason(base_name, stats, score)
        else:
            applied = preset_name
            cfg = apply_dot_noise_strength(PRESETS[preset_name], dot_noise_strength)
            stats = compute_image_stats(source)
            reason = "사용자 프리셋 적용"
        
        anigine_out = render_anigine(source, cfg)
        save_image(out_path, compose_compare(source, anigine_out) if compare else anigine_out)
        print(f"Saved: {out_path.name} ({applied})")
        report_rows.append({
            "image": str(rel), "output": str(out_path.relative_to(output_dir)),
            "base": preset_name if preset_name != "auto" else "auto", "applied": applied, "reason": reason,
            "sat_mean": f"{stats['sat_mean']:.2f}", "edge_density": f"{stats['edge_density']:.4f}", "noise_level": f"{stats['noise_level']:.2f}"
        })
    write_batch_report(output_dir, report_rows)

def main() -> None:
    args = parse_args()
    input_path, output_path = Path(args.input), Path(args.output)
    if input_path.is_file():
        process_single(input_path, output_path, args.preset, args.compare, args.show, args.max_side, args.dot_noise_suppression)
    elif input_path.is_dir():
        process_batch(input_path, output_path, args.preset, args.recursive, args.suffix, args.ext, args.compare, args.max_side, args.dot_noise_suppression)

if __name__ == "__main__":
    main()
