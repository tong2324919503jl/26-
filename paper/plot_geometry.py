"""Rebuild two compact paper figures from the saved, self-created P1/P2 results.

Run with Python and matplotlib; input paths are relative to this file.
Optional --preview-dir writes PNGs for local visual review. No solver results
are overwritten and no new measurements or online requests are generated.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Polygon
import numpy as np

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT))
from problem2.solve import first_region_outer_local, safe_radial_limit

BLUE = "#27647b"
GREY = "#737373"
INK = "#202020"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8.3,
        "mathtext.fontset": "dejavuserif",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.6,
        "lines.linewidth": 1.1,
        "savefig.facecolor": "white",
    })


def finish(fig: plt.Figure, filename: str, preview_dir: Path | None) -> None:
    output = PAPER / "figures"
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / f"{filename}.pdf", bbox_inches="tight", pad_inches=0.04,
                metadata={"Title": filename, "Author": "", "Subject": "Self-created mathematical examples"})
    if preview_dir is not None:
        preview_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview_dir / f"{filename}.png", dpi=180, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def triangle_figure(preview_dir: Path | None) -> None:
    data = read_json(ROOT / "problem1/results/triangle_optical_counterexample.result.json")
    vertices = np.array(data["vertices"])
    endpoints = np.array(data["diameter_endpoints"])
    disk_d = data["diameter_circle"]
    disk_e = data["minimum_enclosing_circle"]
    fig = plt.figure(figsize=(6.4, 3.15))
    ax = fig.add_axes((0.075, 0.18, 0.53, 0.76))
    ax.add_patch(Polygon(vertices, closed=True, facecolor="#e8e8e8", edgecolor=INK, linewidth=1.2))
    ax.add_patch(Circle(disk_d["center"], disk_d["radius_m"], fill=False,
                        edgecolor=BLUE, linewidth=1.4, linestyle=(0, (4, 2))))
    ax.add_patch(Circle(disk_e["center"], disk_e["radius_m"], fill=False,
                        edgecolor=INK, linewidth=1.35))
    ax.plot(*endpoints.T, color=BLUE, linewidth=1.9)
    ax.scatter(*vertices.T, s=20, color=INK, zorder=5)
    ax.scatter(*disk_d["center"], marker="+", s=62, linewidth=1.3, color=BLUE, zorder=6)
    ax.scatter(*disk_e["center"], marker="x", s=32, linewidth=1.1, color=INK, zorder=6)
    for text, xy, offset in (("A", vertices[0], (-12, -8)),
                             ("B", vertices[1], (5, -4)),
                             ("C", vertices[2], (4, 6))):
        ax.annotate(text, xy=xy, xytext=offset, textcoords="offset points", fontsize=9)
    ax.set(xlim=(-13, 49), ylim=(-14, 42), xlabel="$x$ (m)", ylabel="$y$ (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([0, 20, 40])
    ax.set_yticks([0, 20, 40])
    ax.grid(color="#dedede", linewidth=0.45)
    ax.set_axisbelow(True)

    legend_handles = [
        Patch(facecolor="#e8e8e8", edgecolor=INK, label="Bearing-feasible region"),
        Line2D([0], [0], color=BLUE, lw=1.4, ls=(0, (4, 2)), label="Diameter circle"),
        Line2D([0], [0], color=INK, lw=1.3, label="Minimum enclosing circle"),
    ]
    fig.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(0.62, 0.93),
               frameon=False, handlelength=2.4, labelspacing=1.2)
    fig.text(0.65, 0.52, "$D=40$ m\n$D/2=20$ m\n$R_*=23.0940$ m", va="top", linespacing=1.65, fontsize=10)
    fig.text(0.65, 0.24, "$B$ lies outside the\ndiameter circle.", fontsize=9, linespacing=1.4)
    fig.text(0.08, 0.02, r"Constructed from three legal $\pm1^\circ$ bearing observations.", fontsize=8.5)
    finish(fig, "p12_geometry", preview_dir)


def candidate_rows(folder: Path, threshold: float) -> np.ndarray:
    with (folder / "second_point_candidates.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    # Explicitly filter even if the saved shortlist already obeys this limit.
    return np.array([(float(row["local_a_m"]), float(row["local_b_m"]))
                     for row in rows if float(row["diameter_upper_bound_m"]) <= threshold + 1e-7])


def candidates_figure(preview_dir: Path | None) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 4.5))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.9, bottom=0.3, wspace=0.24)
    beta = np.linspace(-89, 89, 1601)
    radii = np.array([safe_radial_limit(float(b)) for b in beta])
    safe_boundary = np.column_stack((radii * np.cos(np.radians(beta)), radii * np.sin(np.radians(beta))))
    folders = [ROOT / "problem2/results", ROOT / "problem2/results/boundary"]
    for index, (ax, folder) in enumerate(zip(axes, folders)):
        plan = read_json(folder / "selection.json")
        station = tuple(plan["first_station_xy_m"])
        theta = plan["first_bearing_deg"]
        prior = np.array(first_region_outer_local(station, theta, plan["error_deg"], plan["circle_sides"]))
        near_best = candidate_rows(folder, plan["candidate_threshold_m"])
        selected = plan["selected"]["local_xy_m"]
        score = plan["selected"]["diameter_upper_bound_m"]
        ax.add_patch(Polygon(safe_boundary, closed=True, facecolor="#eeeeee", edgecolor=INK, linewidth=0.9, zorder=1))
        ax.add_patch(Polygon(prior, closed=True, facecolor=BLUE, edgecolor=BLUE, linewidth=1.15, alpha=0.8, zorder=3))
        ax.scatter(*near_best.T, marker=".", s=6, color="#888888", alpha=0.6, linewidth=0, zorder=4)
        ax.plot([0, selected[0]], [0, selected[1]], color=INK, lw=0.75, zorder=5)
        ax.scatter(*selected, marker="*", s=100, color=INK, edgecolor="white", linewidth=0.5, zorder=6)
        ax.scatter(0, 0, marker="o", s=15, color=INK, zorder=6)
        ax.annotate("$S_1$", (0, 0), (-14, -15), textcoords="offset points")
        ax.annotate("$q_*$", selected, (8, 8), textcoords="offset points", fontsize=10)
        ax.text(780, -690, r"$\mathcal{C}_{\rm safe}$", ha="center", fontsize=11)
        prior_tip = (1150, 0) if index == 0 else (160, 0)
        prior_label = (1250, -300) if index == 0 else (720, -325)
        ax.annotate(r"$\overline{U}_1$", xy=prior_tip, xytext=prior_label,
                    arrowprops={"arrowstyle": "->", "lw": 0.75}, fontsize=11, ha="center")
        if index == 1:
            # This is a source-position constraint; the robot-safe set is
            # intentionally drawn on both sides of the arc.
            ax.add_patch(Circle((-1500, 0), 1800, fill=False, edgecolor=GREY,
                                linewidth=0.9, linestyle=(0, (4, 3)), zorder=2))
            ax.annotate("Source target\nboundary", xy=(110, 800), xytext=(830, 785),
                        arrowprops={"arrowstyle": "->", "lw": 0.65, "color": GREY},
                        fontsize=8, va="center", color="#505050")
        ax.set(xlim=(-100, 1570), ylim=(-950, 950), xlabel="$a$ (m)", ylabel="$b$ (m)")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([0, 500, 1000, 1500])
        ax.set_yticks([-750, 0, 750])
        ax.grid(color="#dddddd", linewidth=0.4)
        ax.set_axisbelow(True)
        ax.set_title(f"({chr(97 + index)}) $S_1=({int(station[0])},0)$ m, $\\theta_1=0^\\circ$", pad=9)
        ax.text(0.5, -0.19, fr"$q_*=({selected[0]:.1f},\,{selected[1]:.1f})$ m" + f"\n$C(q_*)={score:.4f}$ m",
                transform=ax.transAxes, ha="center", va="top", fontsize=8.8, linespacing=1.5)
    fig.legend(handles=[Patch(facecolor="#eeeeee", edgecolor=INK, label="Four-disk safe set"),
                        Patch(facecolor=BLUE, edgecolor=BLUE, label="Source prior outer bound"),
                        Line2D([0], [0], marker=".", color="none", markerfacecolor="#888888", markersize=6, label="Visited points within 10%")],
               loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=3, frameon=False,
               columnspacing=1.4, handlelength=1.5)
    finish(fig, "p2_candidates", preview_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    style()
    triangle_figure(args.preview_dir)
    candidates_figure(args.preview_dir)


if __name__ == "__main__":
    main()
