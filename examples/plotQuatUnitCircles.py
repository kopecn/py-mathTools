import numpy as np
import quaternion

from pyMathTools.constructors.constructUnitSphericalSmallCircle import (
    quat_to_unitSphericalSmallCircle,
)

from pyMathToolsPlotHelpers.plotUnitSphericalSmallCircles import (
    plot_spherical_small_circles_multiplot,
)


def main():

    _ = plot_spherical_small_circles_multiplot(
        circles=[
            quat_to_unitSphericalSmallCircle(q=quaternion.one, radius_angle=np.pi / 8),
            quat_to_unitSphericalSmallCircle(q=quaternion.x, radius_angle=np.pi / 8),
            quat_to_unitSphericalSmallCircle(q=quaternion.y),
            quat_to_unitSphericalSmallCircle(q=quaternion.z),
        ],
        show_plot=True,
    )


if __name__ == "__main__":
    main()
