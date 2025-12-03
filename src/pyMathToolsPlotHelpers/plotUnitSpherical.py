from typing import List, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle
from foundationTypes.mathTypes.UnitSphericalArc import UnitSphericalArc

from pyMathTools.spatial.Quaternion import Quaternion
from pyMathTools.transforms.sphericalTransforms import plate_carree_transform
from pyMathTools.generators.sphericalGenerators import (
    generate_spherical_small_circle_points,
    generate_spherical_arc_points,
    quaternion_to_spherical_vector,
)

deg45 = np.deg2rad(45)
deg90 = np.deg2rad(90)
deg180 = np.deg2rad(180)
deg22_5 = np.pi / 8


def plot_unit_spherical_advanced(
    circles: List[UnitSphericalSmallCircle] | None = None,
    arcs: List[UnitSphericalArc] | None = None,
    quaternions: List[Quaternion] | None = None,
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 6),
    title: str = "Small Circles on Sphere (Flattened)",
    colors: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    show_centers: bool = True,
    show_plot: bool = False,
    ax: Optional[Axes] = None,
) -> Tuple[Figure, Axes]:
    """
    Advanced version with more customization options.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    arcs : List[UnitSphericalArc], optional
        List of UnitSphericalArc objects.
        Each arc starts at (azimuth, polar) and extends along a great circle
        for the specified arc_length (positive or negative)
    quaternions : List[Quaternion], optional
        List of Quaternion objects.
        Each quaternion is visualized as a unit vector from origin to its pointing direction
    num_points : int, optional
        Number of points to generate around each circle
    figsize : tuple, optional
        Figure size (ignored if ax is provided)
    title : str, optional
        Plot title
    colors : list, optional
        List of colors for each circle
    labels : list, optional
        List of labels for each circle
    show_centers : bool, optional
        Whether to show center points (default: True)
    show_plot : bool, optional
        Whether to show the plot (default: False, ignored if ax is provided)
    ax : matplotlib.axes.Axes, optional
        Axes to plot on. If None, creates new figure and axes

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    # Track whether we created the axes or it was provided
    created_ax = ax is None

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.get_figure()

    if circles is not None:
        for idx, circle in enumerate(circles):

            # Generate true spherical small circle points
            azimuth_points, polar_points = generate_spherical_small_circle_points(
                circle, num_points
            )

            # Apply Plate Carrée projection
            x_points, y_points = plate_carree_transform(azimuth_points, polar_points)

            # Determine color and label
            color = colors[idx] if colors is not None and idx < len(colors) else None
            label = labels[idx] if labels is not None and idx < len(labels) else None

            # Plot the circle
            ax.scatter(
                np.degrees(x_points),
                np.degrees(y_points),
                s=10,
                alpha=0.6,
                c=color,
                label=label,
            )

            # Plot center point if requested
            if show_centers:
                x_center, y_center = plate_carree_transform(
                    circle.azimuth, circle.polar
                )
                ax.scatter(
                    np.degrees(x_center),
                    np.degrees(y_center),
                    s=100,
                    marker="x",
                    c=color if color else "red",
                    linewidths=2,
                )

    # Generate points for each arc
    if arcs is not None:
        for idx, arc in enumerate(arcs):

            # Generate spherical arc points
            azimuth_points, polar_points = generate_spherical_arc_points(
                arc, num_points
            )

            # Apply Plate Carrée projection
            x_points, y_points = plate_carree_transform(azimuth_points, polar_points)

            # Determine color and label
            color = colors[idx] if colors is not None and idx < len(colors) else None
            label = labels[idx] if labels is not None and idx < len(labels) else None

            # Plot the arc as a line
            ax.plot(
                np.degrees(x_points),
                np.degrees(y_points),
                linewidth=2,
                alpha=0.8,
                c=color,
                label=label,
                marker="o",
                markersize=3,
            )

    # Plot quaternions as vectors
    if quaternions is not None:
        for idx, quat in enumerate(quaternions):
            # Convert quaternion to spherical coordinates
            _, azimuth, polar = quaternion_to_spherical_vector(quat)

            # Apply Plate Carrée projection to the endpoint
            x_end, y_end = plate_carree_transform(azimuth, polar)

            # Origin is at (0, 0) in this projection
            x_origin, y_origin = plate_carree_transform(0, np.pi / 2)

            # Determine color and label
            color = colors[idx] if colors is not None and idx < len(colors) else None
            label = labels[idx] if labels is not None and idx < len(labels) else None

            if label is None:
                azimuth_deg = np.degrees(azimuth)
                polar_deg = np.degrees(polar)
                label = f"Quat {idx + 1}: w:{quat.w:.1f}, x:{quat.x:.1f}, y:{quat.y:.1f}, z:{quat.z:.1f}"

            # Plot vector as an arrow from origin to the point
            ax.annotate(
                "",
                xy=(np.degrees(x_end), np.degrees(y_end)),
                xytext=(np.degrees(x_origin), np.degrees(y_origin)),
                arrowprops=dict(
                    arrowstyle="->",
                    lw=2,
                    color=color if color else f"C{idx}",
                    alpha=0.8,
                ),
            )

            # Plot endpoint
            ax.scatter(
                np.degrees(x_end),
                np.degrees(y_end),
                s=100,
                marker="*",
                c=color,
                label=label,
                zorder=10,
            )

    # Set up axes
    ax.set_xlabel("Azimuth (deg)", fontsize=12)
    ax.set_ylabel("Latitude (deg)", fontsize=12)
    ax.set_xlim(-180, 180)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set ticks
    ax.set_xticks([-180, -90, 0, 90, 180])
    ax.set_xticklabels(["-180°", "-90°", "0°", "90°", "180°"])

    ax.set_title(title, fontsize=14)

    if labels is not None:
        ax.legend()

    # Only call tight_layout and show if we created the axes
    if created_ax:
        plt.tight_layout()
        if show_plot:
            plt.show()

    return fig, ax


def plot_unit_spherical_polar(
    circles: List[UnitSphericalSmallCircle] | None = None,
    arcs: List[UnitSphericalArc] | None = None,
    quaternions: List[Quaternion] | None = None,
    num_points: int = 120,
    figsize: Tuple[int, int] = (8, 8),
    title: str = "Small Circles on Sphere (Polar View)",
    labels: Optional[List[str]] = None,
    ax: Optional[Axes] = None,
    show_plot: bool = False,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles and arcs on a sphere using polar projection.
    Azimuth is shown as the angle, polar angle is mapped to radius.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    arcs : List[UnitSphericalArc], optional
        List of UnitSphericalArc objects.
        Each arc starts at (azimuth, polar) and extends along a great circle
        for the specified arc_length (positive or negative)
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (8, 8))
    title : str, optional
        Plot title

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    # Track whether we created the axes or it was provided
    created_ax = ax is None

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": "polar"})
    else:
        fig = ax.get_figure()

    if circles is not None:
        for idx, circle in enumerate(circles):

            # Generate true spherical small circle points
            azimuth_points, polar_points = generate_spherical_small_circle_points(
                circle, num_points
            )

            # Map polar angle to radius (0 to 1) for polar plot
            # polar ranges from -pi/2 to pi/2, map to 0 to 1
            radius_points = (polar_points + np.pi / 2) / np.pi

            # Handle azimuth wraparound by detecting large jumps in the ORIGINAL order
            # Insert NaN values at discontinuities to break the line
            azimuth_plot = [azimuth_points[0]]
            radius_plot = [radius_points[0]]

            for i in range(1, len(azimuth_points)):
                # If there's a jump greater than π, we've crossed the -π to π discontinuity
                if abs(azimuth_points[i] - azimuth_points[i - 1]) > np.pi:
                    # Insert NaN to break the line
                    azimuth_plot.append(np.nan)
                    radius_plot.append(np.nan)

                azimuth_plot.append(azimuth_points[i])
                radius_plot.append(radius_points[i])

            # Close the circle by connecting back to the first point
            # Check if we need to handle wraparound at the end
            if abs(azimuth_points[0] - azimuth_points[-1]) > np.pi:
                # Large jump at the end - don't connect
                pass
            else:
                # Normal case - connect back to start
                azimuth_plot.append(azimuth_points[0])
                radius_plot.append(radius_points[0])

            azimuth_plot = np.array(azimuth_plot)
            radius_plot = np.array(radius_plot)

            # Convert radius to degrees for legend
            radius_deg = np.degrees(circle.radius_angle)
            azimuth_deg = np.degrees(circle.azimuth)
            polar_deg = np.degrees(circle.polar)
            label = f"Circle {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, R:{radius_deg:.1f}°"

            # Plot in polar coordinates using plot instead of scatter for continuous lines
            ax.plot(azimuth_plot, radius_plot, linewidth=2, alpha=0.7, label=label)

    # Generate points for each arc
    if arcs is not None:
        for idx, arc in enumerate(arcs):

            # Generate spherical arc points
            azimuth_points, polar_points = generate_spherical_arc_points(
                arc, num_points
            )

            # Map polar angle to radius (0 to 1) for polar plot
            radius_points = (polar_points + np.pi / 2) / np.pi

            # Handle azimuth wraparound
            azimuth_plot = [azimuth_points[0]]
            radius_plot = [radius_points[0]]

            for i in range(1, len(azimuth_points)):
                # If there's a jump greater than π, we've crossed the -π to π discontinuity
                if abs(azimuth_points[i] - azimuth_points[i - 1]) > np.pi:
                    # Insert NaN to break the line
                    azimuth_plot.append(np.nan)
                    radius_plot.append(np.nan)

                azimuth_plot.append(azimuth_points[i])
                radius_plot.append(radius_points[i])

            azimuth_plot = np.array(azimuth_plot)
            radius_plot = np.array(radius_plot)

            # Convert to degrees for legend
            arc_length_deg = np.degrees(arc.arc_length)
            azimuth_deg = np.degrees(arc.azimuth)
            polar_deg = np.degrees(arc.polar)
            orient_deg = np.degrees(arc.orient)
            label = f"Arc {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, L:{arc_length_deg:.1f}°, O:{orient_deg:.1f}°"

            # Plot the arc
            ax.plot(
                azimuth_plot,
                radius_plot,
                linewidth=2,
                alpha=0.8,
                label=label,
                marker="o",
                markersize=3,
            )

    # Plot quaternions as vectors
    if quaternions is not None:
        for idx, quat in enumerate(quaternions):
            # Convert quaternion to spherical coordinates
            _, azimuth, polar = quaternion_to_spherical_vector(quat)

            # Map polar angle to radius (0 to 1) for polar plot
            radius = (polar + np.pi / 2) / np.pi

            # Plot vector as an arrow from origin
            ax.annotate(
                "",
                xy=(azimuth, radius),
                xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", lw=2, color=f"C{idx}", alpha=0.8),
            )

            # Plot endpoint
            azimuth_deg = np.degrees(azimuth)
            polar_deg = np.degrees(polar)
            label = f"Quat {idx + 1}: w:{quat.w:.1f}, x:{quat.x:.1f}, y:{quat.y:.1f}, z:{quat.z:.1f}"

            ax.scatter(azimuth, radius, s=150, marker="*", label=label, zorder=10)

    ax.set_title(title, fontsize=14, pad=20)

    if labels is not None:
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    ax.grid(True, alpha=0.3)

    # Only call tight_layout and show if we created the axes
    if created_ax:
        plt.tight_layout()
        if show_plot:
            plt.show()

    return fig, ax


def plot_unit_spherical_3d(
    circles: List[UnitSphericalSmallCircle] | None = None,
    arcs: List[UnitSphericalArc] | None = None,
    quaternions: List[Quaternion] | None = None,
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 10),
    title: str = "Small Circles on Unit Sphere (3D)",
    show_sphere: bool = True,
    show_legend: bool = True,
    show_plot: bool = False,
    ax: Optional[Axes] = None,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles and arcs on a 3D unit sphere.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    arcs : List[UnitSphericalArc], optional
        List of UnitSphericalArc objects.
        Each arc starts at (azimuth, polar) and extends along a great circle
        for the specified arc_length (positive or negative)
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (10, 10), ignored if ax is provided)
    title : str, optional
        Plot title
    show_sphere : bool, optional
        Whether to show the sphere surface (default: True)
    show_legend : bool, optional
        Whether to show the legend (default: True)
    show_plot : bool, optional
        Whether to show the plot (default: False, ignored if ax is provided)
    ax : matplotlib.axes.Axes, optional
        3D axes to plot on. If None, creates new figure and axes

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    # Track whether we created the axes or it was provided
    created_ax = ax is None

    if ax is None:
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection="3d")
    else:
        fig = ax.get_figure()

    # Optionally plot the sphere surface (physics convention)
    if show_sphere:
        phi = np.linspace(0, 2 * np.pi, 30)  # azimuth
        theta = np.linspace(0, np.pi, 20)  # polar angle from north to south
        x_sphere = np.outer(np.sin(theta), np.cos(phi))
        y_sphere = np.outer(np.sin(theta), np.sin(phi))
        z_sphere = np.outer(np.cos(theta), np.ones(np.size(phi)))
        ax.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color="lightblue")

    # Plot each circle
    if circles is not None:
        for idx, circle in enumerate(circles):

            # Generate true spherical small circle points
            azimuth_points, polar_points = generate_spherical_small_circle_points(
                circle, num_points
            )

            # Convert to Cartesian coordinates (unit sphere, r=1, physics convention)
            # theta (polar) from 0 (north pole) to pi (south pole)
            # phi (azimuth) rotation about Z axis
            x = np.sin(polar_points) * np.cos(azimuth_points)
            y = np.sin(polar_points) * np.sin(azimuth_points)
            z = np.cos(polar_points)

            # Convert radius to degrees for legend
            radius_deg = np.degrees(circle.radius_angle)
            azimuth_deg = np.degrees(circle.azimuth)
            polar_deg = np.degrees(circle.polar)
            label = f"Circle {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, R:{radius_deg:.1f}°"

            # Plot the circle
            ax.scatter(x, y, z, s=10, alpha=0.8, label=label)

    # Plot each arc
    if arcs is not None:
        for idx, arc in enumerate(arcs):

            # Generate spherical arc points
            azimuth_points, polar_points = generate_spherical_arc_points(
                arc, num_points
            )

            # Convert to Cartesian coordinates (unit sphere, r=1, physics convention)
            x = np.sin(polar_points) * np.cos(azimuth_points)
            y = np.sin(polar_points) * np.sin(azimuth_points)
            z = np.cos(polar_points)

            # Convert to degrees for legend
            arc_length_deg = np.degrees(arc.arc_length)
            azimuth_deg = np.degrees(arc.azimuth)
            polar_deg = np.degrees(arc.polar)
            orient_deg = np.degrees(arc.orient)
            label = f"Arc {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, L:{arc_length_deg:.1f}°, O:{orient_deg:.1f}°"

            # Plot the arc as a line
            ax.plot(
                x,
                y,
                z,
                linewidth=2,
                alpha=0.8,
                label=label,
                marker="o",
                markersize=3,
            )

    # Plot quaternions as vectors
    if quaternions is not None:
        for idx, quat in enumerate(quaternions):
            # Convert quaternion to Cartesian coordinates
            cartesian, azimuth, polar = quaternion_to_spherical_vector(quat)
            x, y, z = cartesian

            # Plot vector from origin to the point
            ax.quiver(
                0,
                0,
                0,
                x,
                y,
                z,
                length=1.0,
                arrow_length_ratio=0.15,
                color=f"C{idx}",
                linewidth=2.5,
                alpha=0.9,
            )

            # Plot endpoint
            azimuth_deg = np.degrees(azimuth)
            polar_deg = np.degrees(polar)
            label = f"Quat {idx + 1}: w:{quat.w:.1f}, x:{quat.x:.1f}, y:{quat.y:.1f}, z:{quat.z:.1f}"

            ax.scatter(x, y, z, s=150, marker="*", label=label, zorder=10)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(title, fontsize=14)

    # Add legend if requested, positioned outside the plot area
    if show_legend:
        ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1.0))

    # Set equal aspect ratio
    ax.set_box_aspect([1, 1, 1])

    # Set initial view angle: physics convention with Z up, Y right, X down-left
    # elev=20 looks from slightly above, azim=45 gives the proper orientation
    ax.view_init(elev=20, azim=45)

    # Only call tight_layout and show if we created the axes
    if created_ax:
        plt.tight_layout()
        if show_plot:
            plt.show()

    return fig, ax


def plot_unit_spherical_multiplot(
    circles: List[UnitSphericalSmallCircle] | None = None,
    arcs: List[UnitSphericalArc] | None = None,
    quaternions: List[Quaternion] | None = None,
    num_points: int = 120,
    figsize: Tuple[int, int] = (24, 6),
    title: str = "Small Circles on Unit Sphere - Multiple Views",
    show_plot: bool = False,
) -> Figure:
    """
    Create a multiplot showing Plate Carrée, Top View, and 3D views of spherical small circles.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (24, 6))
    title : str, optional
        Overall title
    show_plot : bool, optional
        Whether to show the plot (default: False)

    Returns:
    --------
    fig : matplotlib figure object
    """
    # Create figure with overall title
    fig = plt.figure(figsize=figsize)
    fig.suptitle(title, fontsize=16)

    # Create subplots
    ax1 = fig.add_subplot(131)  # Plate Carrée projection
    ax2 = fig.add_subplot(132, projection="polar")  # Top view
    ax3 = fig.add_subplot(133, projection="3d")  # 3D view

    # 1. Plate Carrée projection using advanced plot function
    plot_unit_spherical_advanced(
        circles=circles,
        arcs=arcs,
        quaternions=quaternions,
        num_points=num_points,
        title="Plate Carrée Projection",
        show_centers=False,
        ax=ax1,
    )
    # Customize for multiplot
    ax1.set_xlabel("Azimuth (deg)", fontsize=10)
    ax1.set_ylabel("Latitude (deg)", fontsize=10)
    ax1.set_title("Plate Carrée Projection", fontsize=12)

    # 2. Top view (looking down z-axis)
    plot_unit_spherical_polar(
        circles=circles,
        arcs=arcs,
        quaternions=quaternions,
        num_points=num_points,
        title="Top View (Down Z-Axis)",
        ax=ax2,
    )
    # Customize for multiplot
    ax2.set_xlabel("Azimuth (deg)", fontsize=10)
    ax2.set_ylabel("Latitude (deg)", fontsize=10)
    ax2.set_title("Top View (Down Z-Axis)", fontsize=12)

    # 3. 3D view
    plot_unit_spherical_3d(
        circles=circles,
        arcs=arcs,
        quaternions=quaternions,
        num_points=num_points,
        title="3D View",
        show_sphere=True,
        show_legend=True,
        ax=ax3,
    )
    # Customize for multiplot
    ax3.set_xlabel("X", fontsize=10)
    ax3.set_ylabel("Y", fontsize=10)
    ax3.set_zlabel("Z", fontsize=10)
    ax3.set_title("3D View", fontsize=12)
    # Position legend outside plot area with smaller font
    ax3.legend(loc="upper left", bbox_to_anchor=(1.05, 1.0), fontsize=8)

    plt.tight_layout()

    if show_plot:
        plt.show()

    return fig


def demo() -> None:
    """Demonstration of multiplot view showing spherical small circles in three different projections."""

    # Define 4 circles using UnitSphericalSmallCircle dataclass
    circles: List[UnitSphericalSmallCircle] = [
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=0,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=np.pi / 2,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=np.pi,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=-np.pi / 2,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=-np.pi / 2,
            polar=np.pi / 2,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=np.pi / 2,
            polar=np.pi / 2,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=-deg45,
            polar=deg45,
            radius_angle=deg45,
        ),
        UnitSphericalSmallCircle(
            azimuth=np.deg2rad(135),
            polar=deg45,
            radius_angle=deg45,
        ),
    ]

    arcs: List[UnitSphericalArc] = [
        UnitSphericalArc(orient=0, azimuth=0, polar=0, arc_length=deg22_5),
        UnitSphericalArc(orient=deg45, azimuth=0, polar=0, arc_length=deg22_5),
        UnitSphericalArc(orient=deg90, azimuth=0, polar=0, arc_length=deg22_5),
        UnitSphericalArc(orient=0, azimuth=0, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=0, azimuth=deg45, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=0, azimuth=deg90, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg45, azimuth=0, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg45, azimuth=deg45, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg45, azimuth=deg90, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg90, azimuth=0, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg90, azimuth=deg45, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=deg90, azimuth=deg90, polar=deg45, arc_length=deg22_5),
        UnitSphericalArc(orient=0, azimuth=0, polar=deg45, arc_length=-deg22_5),
        UnitSphericalArc(orient=0, azimuth=deg45, polar=deg45, arc_length=-deg22_5),
        UnitSphericalArc(orient=0, azimuth=deg90, polar=deg45, arc_length=-deg22_5),
    ]

    quats: List[Quaternion] = [
        Quaternion.from_components(w=1, x=0, y=0, z=0),
        Quaternion.from_components(w=0, x=1, y=0, z=0),
        Quaternion.from_components(w=0, x=0, y=1, z=0),
        Quaternion.from_components(w=0, x=0, y=0, z=1),
        Quaternion.from_components(w=0, x=0.707, y=0, z=0.707),
        Quaternion.from_components(w=0, x=0.707, y=0.707, z=0),
        Quaternion.from_components(w=0, x=0, y=0.707, z=0.707),
        Quaternion.from_components(w=0.707, x=0.707, y=0, z=0),
        Quaternion.from_components(w=0.707, x=0, y=0.707, z=0),
        Quaternion.from_components(w=0.707, x=0, y=0, z=0.707),
        Quaternion.from_components(w=0, x=0.577, y=-0.577, z=0.577),
    ]

    _ = plot_unit_spherical_multiplot(
        # circles=circles,
        # arcs=arcs,
        quaternions=quats,
        show_plot=True,
    )


if __name__ == "__main__":
    demo()
