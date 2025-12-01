from typing import List, Union
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from foundationTypes.mathTypes.UnitSphericalSmallCircle import UnitSphericalSmallCircle


def generate_spherical_small_circle_points(azimuth_center, polar_center, radius_angle, num_points=120):
    """
    Generate points on a true small circle on a unit sphere.

    A small circle is the set of all points at a fixed angular distance (radius_angle)
    from a center point on the sphere.

    Parameters:
    -----------
    azimuth_center : float
        Azimuth angle of circle center (radians, 0 to 2π)
    polar_center : float
        Polar angle of circle center (radians, -π/2 to π/2)
    radius_angle : float
        Angular radius of the circle (radians)
    num_points : int
        Number of points to generate around the circle

    Returns:
    --------
    azimuth_points : ndarray
        Azimuth angles of points on the circle
    polar_points : ndarray
        Polar angles of points on the circle
    """
    # Convert center to Cartesian coordinates
    x_center = np.cos(polar_center) * np.cos(azimuth_center)
    y_center = np.cos(polar_center) * np.sin(azimuth_center)
    z_center = np.sin(polar_center)
    center = np.array([x_center, y_center, z_center])

    # Create orthonormal basis at the center point
    # North pole direction
    north = np.array([0, 0, 1])

    # Tangent vector 1 (east direction)
    if np.abs(z_center) < 0.999:  # Not at poles
        east = np.cross(north, center)
        east = east / np.linalg.norm(east)
    else:  # At poles, use arbitrary east direction
        east = np.array([1, 0, 0])

    # Tangent vector 2 (north direction in tangent plane)
    north_tangent = np.cross(center, east)
    north_tangent = north_tangent / np.linalg.norm(north_tangent)

    # Generate points around the circle
    theta = np.linspace(0, 2 * np.pi, num_points)

    # Points on the small circle using rotation
    # The small circle is at angular distance radius_angle from center
    azimuth_points = np.zeros(num_points)
    polar_points = np.zeros(num_points)

    for i, t in enumerate(theta):
        # Local coordinates: move radius_angle away from center in direction t
        local_direction = np.cos(t) * east + np.sin(t) * north_tangent

        # Rotate center point toward local_direction by radius_angle
        # Using Rodrigues' rotation formula
        axis = np.cross(center, local_direction)
        axis_norm = np.linalg.norm(axis)

        if axis_norm > 1e-10:
            axis = axis / axis_norm
            # Rotate center around axis by radius_angle
            cos_angle = np.cos(radius_angle)
            sin_angle = np.sin(radius_angle)

            point = (cos_angle * center +
                    sin_angle * np.cross(axis, center) +
                    (1 - cos_angle) * np.dot(axis, center) * axis)
        else:
            # If no rotation needed (shouldn't happen)
            point = center

        # Convert back to spherical coordinates
        x, y, z = point
        r = np.sqrt(x**2 + y**2 + z**2)
        x, y, z = x/r, y/r, z/r  # Normalize to unit sphere

        polar_points[i] = np.arcsin(np.clip(z, -1, 1))
        azimuth_points[i] = np.arctan2(y, x)
        if azimuth_points[i] < 0:
            azimuth_points[i] += 2 * np.pi

    return azimuth_points, polar_points


def mercator_projection(azimuth, polar):
    """
    Apply Mercator projection to spherical coordinates.

    Parameters:
    -----------
    azimuth : float or ndarray
        Azimuth angle(s) in radians (0 to 2π)
    polar : float or ndarray
        Polar angle(s) in radians (-π/2 to π/2)

    Returns:
    --------
    x : float or ndarray
        Mercator x coordinate (longitude)
    y : float or ndarray
        Mercator y coordinate (latitude projection)
    """
    x = azimuth
    # Mercator projection: y = ln(tan(π/4 + lat/2))
    # Clamp polar to avoid infinities at poles
    polar_clamped = np.clip(polar, -np.pi/2 + 0.001, np.pi/2 - 0.001)
    y = np.log(np.tan(np.pi/4 + polar_clamped/2))
    return x, y


def plot_spherical_small_circles(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points=120,
    figsize=(10, 6),
    title="Small Circles on Sphere (Mercator Projection)",
):
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
        x_points, y_points = mercator_projection(azimuth_points, polar_points)

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot the circle
        ax.scatter(x_points, y_points, s=10, alpha=0.6, label=label)

    # Set up axes
    ax.set_xlabel("Longitude (radians)", fontsize=12)
    ax.set_ylabel("Mercator Y", fontsize=12)
    ax.set_xlim(0, 2 * np.pi)

    # Add grid
    ax.grid(True, alpha=0.3)

    # Set x-axis ticks to show multiples of pi
    ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
    ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])

    ax.set_title(title, fontsize=14)

    # Add legend
    ax.legend()

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_advanced(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points=120,
    figsize=(10, 6),
    title="Small Circles on Sphere (Flattened)",
    colors=None,
    labels=None,
    show_centers=True,
):
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
        x_points, y_points = mercator_projection(azimuth_points, polar_points)

        # Determine color and label
        color = colors[idx] if colors is not None and idx < len(colors) else None
        label = labels[idx] if labels is not None and idx < len(labels) else None

        # Plot the circle
        ax.scatter(x_points, y_points, s=10, alpha=0.6, c=color, label=label)

        # Plot center point if requested
        if show_centers:
            x_center, y_center = mercator_projection(azimuth_center, polar_center)
            ax.scatter(
                x_center,
                y_center,
                s=100,
                marker="x",
                c=color if color else "red",
                linewidths=2,
            )

    # Set up axes
    ax.set_xlabel("Longitude (radians)", fontsize=12)
    ax.set_ylabel("Mercator Y", fontsize=12)
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


def plot_spherical_small_circles_polar(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points=120,
    figsize=(8, 8),
    title="Small Circles on Sphere (Polar View)",
):
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
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={'projection': 'polar'})

    # Convert UnitSphericalSmallCircle objects to arrays if needed
    if circles and isinstance(circles[0], UnitSphericalSmallCircle):
        circles = [[c.azimuth, c.polar, c.radius_angle] for c in circles]

    circles = np.array(circles)
    if circles.ndim == 1:
        circles = circles.reshape(1, -1)

    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate angles around the circle
        theta = np.linspace(0, 2 * np.pi, num_points)

        # Generate circle points in spherical space
        azimuth_points = azimuth_center + radius_angle * np.cos(theta)
        polar_points = polar_center + radius_angle * np.sin(theta)

        # Handle wrapping for azimuth (0 to 2*pi)
        azimuth_points = np.mod(azimuth_points, 2 * np.pi)

        # Clip polar angle to valid range (-pi/2 to pi/2)
        polar_points = np.clip(polar_points, -np.pi / 2, np.pi / 2)

        # Map polar angle to radius (0 to 1)
        # polar ranges from -pi/2 to pi/2, map to 0 to 1
        radius_points = (polar_points + np.pi / 2) / np.pi

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot in polar coordinates
        ax.scatter(azimuth_points, radius_points, s=10, alpha=0.6, label=label)

    ax.set_title(title, fontsize=14, pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_3d(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points=120,
    figsize=(10, 10),
    title="Small Circles on Unit Sphere (3D)",
    show_sphere=True,
):
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

    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection='3d')

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
        ax.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color='lightblue')

    # Plot each circle
    for idx, circle in enumerate(circles):
        azimuth_center, polar_center, radius_angle = circle

        # Generate points around the small circle on the sphere
        theta = np.linspace(0, 2 * np.pi, num_points)

        # Generate circle points in spherical coordinates
        azimuth_points = azimuth_center + radius_angle * np.cos(theta)
        polar_points = polar_center + radius_angle * np.sin(theta)

        # Handle wrapping and clipping
        azimuth_points = np.mod(azimuth_points, 2 * np.pi)
        polar_points = np.clip(polar_points, -np.pi / 2, np.pi / 2)

        # Convert to Cartesian coordinates (unit sphere, r=1)
        x = np.cos(polar_points) * np.cos(azimuth_points)
        y = np.cos(polar_points) * np.sin(azimuth_points)
        z = np.sin(polar_points)

        # Convert radius to degrees for legend
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"

        # Plot the circle
        ax.scatter(x, y, z, s=10, alpha=0.8, label=label)

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(title, fontsize=14)
    ax.legend()

    # Set equal aspect ratio
    ax.set_box_aspect([1, 1, 1])

    plt.tight_layout()

    return fig, ax


def plot_spherical_small_circles_multiplot(
    circles: Union[List[UnitSphericalSmallCircle], List[List[float]]],
    num_points=120,
    figsize=(18, 6),
    title="Small Circles on Unit Sphere - Multiple Views",
):
    """
    Create a multiplot showing flattened, polar, and 3D views of spherical small circles.

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

    # 1. Flattened view
    ax1 = fig.add_subplot(131)
    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        theta = np.linspace(0, 2 * np.pi, num_points)
        azimuth_points = azimuth_center + radius_angle * np.cos(theta)
        polar_points = polar_center + radius_angle * np.sin(theta)
        azimuth_points = np.mod(azimuth_points, 2 * np.pi)
        polar_points = np.clip(polar_points, -np.pi / 2, np.pi / 2)
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        ax1.scatter(azimuth_points, polar_points, s=10, alpha=0.6, label=label)

    ax1.set_xlabel("Azimuthal Angle (radians)", fontsize=10)
    ax1.set_ylabel("Polar Angle (radians)", fontsize=10)
    ax1.set_xlim(0, 2 * np.pi)
    ax1.set_ylim(-np.pi / 2, np.pi / 2)
    ax1.grid(True, alpha=0.3)
    ax1.set_title("Flattened View", fontsize=12)
    ax1.legend(fontsize=8)

    # 2. Polar view
    ax2 = fig.add_subplot(132, projection='polar')
    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        theta = np.linspace(0, 2 * np.pi, num_points)
        azimuth_points = azimuth_center + radius_angle * np.cos(theta)
        polar_points = polar_center + radius_angle * np.sin(theta)
        azimuth_points = np.mod(azimuth_points, 2 * np.pi)
        polar_points = np.clip(polar_points, -np.pi / 2, np.pi / 2)
        radius_points = (polar_points + np.pi / 2) / np.pi
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        ax2.scatter(azimuth_points, radius_points, s=10, alpha=0.6, label=label)

    ax2.set_title("Polar View", fontsize=12, pad=20)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8, loc='upper right', bbox_to_anchor=(1.2, 1.1))

    # 3. 3D view
    ax3 = fig.add_subplot(133, projection='3d')

    # Plot sphere surface
    u = np.linspace(0, 2 * np.pi, 30)
    v = np.linspace(-np.pi / 2, np.pi / 2, 20)
    x_sphere = np.outer(np.cos(v), np.cos(u))
    y_sphere = np.outer(np.cos(v), np.sin(u))
    z_sphere = np.outer(np.sin(v), np.ones(np.size(u)))
    ax3.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.1, color='lightblue')

    for idx, circle in enumerate(circles_array):
        azimuth_center, polar_center, radius_angle = circle
        theta = np.linspace(0, 2 * np.pi, num_points)
        azimuth_points = azimuth_center + radius_angle * np.cos(theta)
        polar_points = polar_center + radius_angle * np.sin(theta)
        azimuth_points = np.mod(azimuth_points, 2 * np.pi)
        polar_points = np.clip(polar_points, -np.pi / 2, np.pi / 2)
        x = np.cos(polar_points) * np.cos(azimuth_points)
        y = np.cos(polar_points) * np.sin(azimuth_points)
        z = np.sin(polar_points)
        radius_deg = np.degrees(radius_angle)
        label = f"Circle {idx + 1}: {radius_deg:.1f}°"
        ax3.scatter(x, y, z, s=10, alpha=0.8, label=label)

    ax3.set_xlabel('X', fontsize=10)
    ax3.set_ylabel('Y', fontsize=10)
    ax3.set_zlabel('Z', fontsize=10)
    ax3.set_title("3D View", fontsize=12)
    ax3.legend(fontsize=8)
    ax3.set_box_aspect([1, 1, 1])

    plt.tight_layout()

    return fig


def demo():
    """Demonstration of multiplot view showing spherical small circles in three different projections."""

    # Define 4 circles using UnitSphericalSmallCircle dataclass
    circles = [
        UnitSphericalSmallCircle(
            azimuth=0,
            polar=0,
            radius_angle=0.6,  # Circle at origin (0°, equator) with large radius
        ),
        UnitSphericalSmallCircle(
            azimuth=np.pi,  # 180°
            polar=np.pi / 4,  # 45° north
            radius_angle=0.2,
        ),
        UnitSphericalSmallCircle(
            azimuth=3 * np.pi / 2,  # 270°
            polar=-np.pi / 6,  # -30° south
            radius_angle=0.25,
        ),
        UnitSphericalSmallCircle(
            azimuth=0,  # 0°
            polar=-np.pi / 2,  # -90° south pole
            radius_angle=np.pi / 2,
        ),
    ]

    # Create the multiplot showing all three views
    fig = plot_spherical_small_circles_multiplot(
        circles,
        num_points=240,
        title="Unit Spherical Small Circles - Flattened, Polar, and 3D Views"
    )

    # Show the plot
    plt.show()


if __name__ == "__main__":
    demo()
