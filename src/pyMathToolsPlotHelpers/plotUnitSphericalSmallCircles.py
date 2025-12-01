from typing import List, Union, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle

from pyMathTools.transforms.sphericalTransforms import (
    mercator_transform,
    gauss_kruger_transform,
)
from pyMathTools.generators.sphericalGenerators import (
    generate_spherical_small_circle_points,
)


def plot_spherical_small_circles(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 6),
    title: str = "Small Circles on Sphere (Mercator Projection)",
    show_legend: bool = True,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles on a sphere using Mercator projection.

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

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    # Convert to numpy array
    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    # Generate points for each circle
    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )

        # Apply Mercator projection
        x_points, y_points = mercator_transform(azimuth_points, polar_points)

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot the circle
        ax.scatter(x_points, y_points, s=10, alpha=0.6, label=label)

    # Set up axes
    ax.set_xlabel("Azmuth (radians)", fontsize=12)
    ax.set_ylabel("Polar (radians)", fontsize=12)
    ax.set_xlim(0, 2 * np.pi)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set x-axis ticks to show multiples of pi
    ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
    ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])

    ax.set_title(title, fontsize=14)

    # Add legend if requested
    if show_legend:
        ax.legend()

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_advanced(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 6),
    title: str = "Small Circles on Sphere (Flattened)",
    colors: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    show_centers: bool = True,
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
        Figure size
    title : str, optional
        Plot title
    colors : list, optional
        List of colors for each circle
    labels : list, optional
        List of labels for each circle
    show_centers : bool, optional
        Whether to show center points (default: True)

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )

        # Apply Mercator projection
        x_points, y_points = mercator_transform(azimuth_points, polar_points)

        # Determine color and label
        color = colors[idx] if colors is not None and idx < len(colors) else None
        label = labels[idx] if labels is not None and idx < len(labels) else None

        # Plot the circle
        ax.scatter(x_points, y_points, s=10, alpha=0.6, c=color, label=label)

        # Plot center point if requested
        if show_centers:
            x_center, y_center = mercator_transform(azimuth_center, polar_center)
            ax.scatter(
                x_center,
                y_center,
                s=100,
                marker="x",
                c=color if color else "red",
                linewidths=2,
            )

    # Set up axes
    ax.set_xlabel("Azmuth (radians)", fontsize=12)
    ax.set_ylabel("Polar (radians)", fontsize=12)
    ax.set_xlim(0, 2 * np.pi)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set ticks
    ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
    ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])

    ax.set_title(title, fontsize=14)

    if labels is not None:
        ax.legend()

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_gauss_kruger(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 6),
    title: str = "Small Circles on Sphere (Gauss-Krüger Projection)",
    central_meridian: float = np.pi,
    show_legend: bool = True,
) -> Tuple[Figure, Axes]:
    """
    Plot small circles on a sphere using Gauss-Krüger (Transverse Mercator) projection.

    Parameters:
    -----------
    circles : List[UnitSphericalSmallCircle] or array-like
        List of UnitSphericalSmallCircle objects or array of [azimuth, polar, radius] lists
    num_points : int, optional
        Number of points to generate around each circle (default: 120)
    figsize : tuple, optional
        Figure size (default: (10, 6))
    title : str, optional
        Plot title
    central_meridian : float, optional
        Central meridian in radians (default: π)
    show_legend : bool, optional
        Whether to show the legend (default: True)

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )

        # Apply Gauss-Krüger projection
        easting, northing = gauss_kruger_transform(
            azimuth_points, polar_points, central_meridian
        )

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot with swapped coordinates to view down at equator
        # x-axis (azimuth-related) = northing
        # y-axis (polar-related) = easting
        ax.scatter(northing, easting, s=10, alpha=0.6, label=label)

    ax.set_xlabel("Azimuth-related (radians)", fontsize=12)
    ax.set_ylabel("Polar-related (radians)", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_title(title, fontsize=14)
    ax.set_aspect("equal", adjustable="box")

    # Add legend if requested
    if show_legend:
        ax.legend()

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_polar(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (8, 8),
    title: str = "Small Circles on Sphere (Polar View)",
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

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )

        # Map polar angle to radius (0 to 1) for polar plot
        # polar ranges from -pi/2 to pi/2, map to 0 to 1
        radius_points = (polar_points + np.pi / 2) / np.pi

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot in polar coordinates
        ax.scatter(azimuth_points, radius_points, s=10, alpha=0.6, label=label)

    ax.set_title(title, fontsize=14, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_3d(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (10, 10),
    title: str = "Small Circles on Unit Sphere (3D)",
    show_sphere: bool = True,
    show_legend: bool = True,
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
        Figure size (default: (10, 10))
    title : str, optional
        Plot title
    show_sphere : bool, optional
        Whether to show the sphere surface (default: True)
    show_legend : bool, optional
        Whether to show the legend (default: True)

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    # Optionally plot the sphere surface
    if show_sphere:
        u = np.linspace(0, 2 * np.pi, 30)
        v = np.linspace(-np.pi / 2, np.pi / 2, 20)
        x_sphere = np.outer(np.cos(v), np.cos(u))
        y_sphere = np.outer(np.cos(v), np.sin(u))
        z_sphere = np.outer(np.sin(v), np.ones(np.size(u)))
        ax.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color="lightblue")

    # Plot each circle
    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate true spherical small circle points
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )

        # Convert to Cartesian coordinates (unit sphere, r=1)
        x = np.cos(polar_points) * np.cos(azimuth_points)
        y = np.cos(polar_points) * np.sin(azimuth_points)
        z = np.sin(polar_points)

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot the circle
        ax.scatter(x, y, z, s=10, alpha=0.8, label=label)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(title, fontsize=14)

    # Add legend if requested
    if show_legend:
        ax.legend()

    # Set equal aspect ratio
    ax.set_box_aspect([1, 1, 1])

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_multiplot(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points: int = 120,
    figsize: Tuple[int, int] = (18, 6),
    title: str = "Small Circles on Unit Sphere - Multiple Views",
) -> Figure:
    """
    Create a multiplot showing Mercator, Gauss-Krüger, and 3D views of spherical small circles.

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

    Returns:
    --------
    fig : matplotlib figure object
    """
    fig = plt.figure(figsize=figsize)
    fig.suptitle(title, fontsize=16)

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    circles_array = circles
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles_array = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles_array = np.array(circles_array)
    if circles_array.ndim == 1:
        circles_array = circles_array.reshape(1, -1)

    # 1. Mercator projection view
    ax1 = fig.add_subplot(131)
    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )
        x_points, y_points = mercator_transform(azimuth_points, polar_points)
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        ax1.scatter(x_points, y_points, s=10, alpha=0.6, label=label)

    ax1.set_xlabel("Azmuth (radians)", fontsize=10)
    ax1.set_ylabel("Polar (radians)", fontsize=10)
    ax1.set_xlim(0, 2 * np.pi)
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Mercator Projection", fontsize=12)
    # No legend in Mercator view

    # 2. Gauss-Krüger view
    ax2 = fig.add_subplot(132)
    central_meridian = np.pi  # Central meridian at 180°
    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )
        easting, northing = gauss_kruger_transform(
            azimuth_points, polar_points, central_meridian
        )
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        # Swap coordinates: x=northing (azimuth-related), y=easting (polar-related)
        ax2.scatter(northing, easting, s=10, alpha=0.6, label=label)

    ax2.set_xlabel("Azimuth-related (radians)", fontsize=10)
    ax2.set_ylabel("Polar-related (radians)", fontsize=10)
    ax2.set_title("Gauss-Krüger Projection", fontsize=12)
    ax2.set_aspect("equal", adjustable="box")
    ax2.grid(True, alpha=0.3)
    # No legend in Gauss-Krüger view

    # 3. 3D view
    ax3 = fig.add_subplot(133, projection="3d")

    # Plot sphere surface
    u = np.linspace(0, 2 * np.pi, 30)
    v = np.linspace(-np.pi / 2, np.pi / 2, 20)
    x_sphere = np.outer(np.cos(v), np.cos(u))
    y_sphere = np.outer(np.cos(v), np.sin(u))
    z_sphere = np.outer(np.sin(v), np.ones(np.size(u)))
    ax3.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color="lightblue")

    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        azimuth_points, polar_points = generate_spherical_small_circle_points(
            azimuth_center, polar_center, radius_angle, num_points
        )
        x = np.cos(polar_points) * np.cos(azimuth_points)
        y = np.cos(polar_points) * np.sin(azimuth_points)
        z = np.sin(polar_points)
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        ax3.scatter(x, y, z, s=10, alpha=0.8, label=label)

    ax3.set_xlabel("X", fontsize=10)
    ax3.set_ylabel("Y", fontsize=10)
    ax3.set_zlabel("Z", fontsize=10)
    ax3.set_title("3D View", fontsize=12)
    ax3.legend(fontsize=8)
    ax3.set_box_aspect([1, 1, 1])

    plt.tight_layout()

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
            polar=np.deg2rad(-90),
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=np.deg2rad(90),
            polar=0,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=np.deg2rad(-90),
            polar=0,
            radius_angle=np.deg2rad(45),
        ),
        UnitSphericalSmallCircle(
            azimuth=np.deg2rad(30),
            polar=np.deg2rad(30),
            radius_angle=np.deg2rad(30),
        ),
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
    fig = plot_spherical_small_circles_multiplot(
        circles,
        num_points=240,
        title="Unit Spherical Small Circles - Mercator, Gauss-Krüger, and 3D Views",
    )

    # Show the plot
    plt.show()


if __name__ == "__main__":
    demo()
