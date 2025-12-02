from typing import List, Union, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.transforms.sphericalTransforms import plate_carree_transform
from pyMathTools.generators.sphericalGenerators import (
    generate_spherical_small_circle_points,
)


def plot_spherical_small_circles(
    circles: List[UnitSphericalSmallCircle],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 6),
    title: str = "Small Circles on Sphere (Plate Carrée Projection)",
    show_legend: bool = True,
    show_plot: bool = False,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles on a sphere using plate carrée (equirectangular) projection.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists.
        Each circle represents a small circle on the unit sphere
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (10, 6))
    title : str, optional
        Plot title
    show_legend : bool, optional
        Whether to show the legend (default: True)

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Generate points for each circle
    for idx, circle in enumerate(circles):

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            circle, num_points
        )

        # Apply Plate Carrée projection
        x_points, y_points = plate_carree_transform(azimuth_points, polar_points)

        # Convert radius to degrees for legend
        radius_deg = np.degrees(circle.radius_angle)
        azimuth_deg = np.degrees(circle.azimuth)
        polar_deg = np.degrees(circle.polar)
        label = f"Circle {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, R:{radius_deg:.1f}°"

        # Plot the circle
        ax.scatter(
            np.degrees(x_points),
            np.degrees(y_points),
            s=10,
            alpha=0.6,
            label=label,
        )

    # Set up axes
    ax.set_xlabel("Azimuth (deg)", fontsize=12)
    ax.set_ylabel("Latitude (deg)", fontsize=12)
    ax.set_xlim(0, 180)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set x-axis ticks
    ax.set_xticks([0, 90, 180, 270, 360])
    ax.set_xticklabels(["0°", "90°", "180°", "270°", "360°"])

    ax.set_title(title, fontsize=14)

    # Add legend if requested
    if show_legend:
        ax.legend()

    plt.tight_layout()

    if show_plot:
        plt.show()

    return fig, ax


def plot_spherical_small_circles_advanced(
    circles: List[UnitSphericalSmallCircle],
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
            x_center, y_center = plate_carree_transform(circle.azimuth, circle.polar)
            ax.scatter(
                np.degrees(x_center),
                np.degrees(y_center),
                s=100,
                marker="x",
                c=color if color else "red",
                linewidths=2,
            )

    # Set up axes
    ax.set_xlabel("Azimuth (deg)", fontsize=12)
    ax.set_ylabel("Latitude (deg)", fontsize=12)
    ax.set_xlim(0, 180)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set ticks
    ax.set_xticks([0, 90, 180, 270, 360])
    ax.set_xticklabels(["0°", "90°", "180°", "270°", "360°"])

    ax.set_title(title, fontsize=14)

    if labels is not None:
        ax.legend()

    # Only call tight_layout and show if we created the axes
    if created_ax:
        plt.tight_layout()
        if show_plot:
            plt.show()

    return fig, ax


def plot_spherical_small_circles_polar(
    circles: List[UnitSphericalSmallCircle],
    num_points: int = 120,
    figsize: Tuple[int, int] = (8, 8),
    title: str = "Small Circles on Sphere (Polar View)",
    show_plot: bool = False,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles on a sphere using polar projection.
    Azimuth is shown as the angle, polar angle is mapped to radius.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
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
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": "polar"})

    for idx, circle in enumerate(circles):

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            circle, num_points
        )

        # Map polar angle to radius (0 to 1) for polar plot
        # polar ranges from -pi/2 to pi/2, map to 0 to 1
        radius_points = (polar_points + np.pi / 2) / np.pi

        # Convert radius to degrees for legend
        radius_deg = np.degrees(circle.radius_angle)
        azimuth_deg = np.degrees(circle.azimuth)
        polar_deg = np.degrees(circle.polar)
        label = f"Circle {idx + 1}: A:{azimuth_deg:.1f}°, P:{polar_deg:.1f}°, R:{radius_deg:.1f}°"

        # Plot in polar coordinates
        ax.scatter(azimuth_points, radius_points, s=10, alpha=0.6, label=label)

    ax.set_title(title, fontsize=14, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if show_plot:
        plt.show()

    return fig, ax


def plot_spherical_small_circles_3d(
    circles: List[UnitSphericalSmallCircle],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 10),
    title: str = "Small Circles on Unit Sphere (3D)",
    show_sphere: bool = True,
    show_legend: bool = True,
    show_plot: bool = False,
    ax: Optional[Axes] = None,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles on a 3D unit sphere.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
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


def plot_spherical_small_circles_multiplot(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (18, 6),
    title: str = "Small Circles on Unit Sphere - Multiple Views",
    show_plot: bool = False,
) -> Figure:
    """
    Create a multiplot showing Plate Carrée, Gauss-Krüger, and 3D views of spherical small circles.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (18, 6))
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
    ax1 = fig.add_subplot(121)  # Plate Carrée projection
    ax2 = fig.add_subplot(122, projection="3d")  # 3D view

    # 1. Plate Carrée projection using advanced plot function
    plot_spherical_small_circles_advanced(
        circles=circles,
        num_points=num_points,
        title="Plate Carrée Projection",
        show_centers=False,
        ax=ax1,
    )
    # Customize for multiplot
    ax1.set_xlabel("Azimuth (radians)", fontsize=10)
    ax1.set_ylabel("Latitude (radians)", fontsize=10)
    ax1.set_title("Plate Carrée Projection", fontsize=12)

    # 2. 3D view
    plot_spherical_small_circles_3d(
        circles=circles,
        num_points=num_points,
        title="3D View",
        show_sphere=True,
        show_legend=True,
        ax=ax2,
    )
    # Customize for multiplot
    ax2.set_xlabel("X", fontsize=10)
    ax2.set_ylabel("Y", fontsize=10)
    ax2.set_zlabel("Z", fontsize=10)
    ax2.set_title("3D View", fontsize=12)
    # Position legend outside plot area with smaller font
    ax2.legend(loc="upper left", bbox_to_anchor=(1.05, 1.0), fontsize=8)

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
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=np.pi / 2,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=np.pi,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=-np.pi / 2,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=-np.pi / 2,
            polar=np.pi / 2,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=np.pi / 2,
            polar=np.pi / 2,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=-np.deg2rad(45),
            polar=np.deg2rad(45),
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=np.deg2rad(135),
            polar=np.deg2rad(45),
            radius_angle=np.deg2rad(45),
        ),
        # UnitSphericalSmallCircle(  # should overlap circle 1
        #     azimuth=np.pi / 2,
        #     polar=0,
        #     radius_angle=np.deg2rad(45),
        # ),
        # UnitSphericalSmallCircle(
        #     azimuth=np.deg2rad(10),
        #     polar=np.deg2rad(-80),
        #     radius_angle=np.deg2rad(45),
        # ),
        # UnitSphericalSmallCircle(
        #     azimuth=np.deg2rad(10),
        #     polar=np.deg2rad(80),
        #     radius_angle=np.deg2rad(45),
        # ),
        # UnitSphericalSmallCircle(
        #     azimuth=np.pi,  # 180°
        #     polar=np.pi / 4,  # 45° north
        #     radius_angle=0.2,
        # ),
        # UnitSphericalSmallCircle(
        #     azimuth=3 * np.pi / 2,  # 270°
        #     polar=-np.pi / 6,  # -30° south
        #     radius_angle=0.25,
        # ),
    ]

    # Create the multiplot showing all three views
    _ = plot_spherical_small_circles_multiplot(
        circles,
        num_points=240,
        title="Unit Spherical Small Circles - Plate Carrée, Gauss-Krüger, and 3D Views",
        show_plot=True,
    )

    _ = plot_spherical_small_circles(
        circles=circles,
        show_plot=True,
    )

    _ = plot_spherical_small_circles_polar(
        circles=circles,
        show_plot=True,
    )


if __name__ == "__main__":
    demo()
