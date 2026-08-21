from __future__ import annotations

import numpy as np
import pytest

from seeingbench.rendering.projection import (
    apply_local_orthographic_projection,
    local_orthographic_projection_matrix,
)


def test_local_orthographic_projection_matrix_is_identity_at_disk_center() -> None:
    matrix, incidence = local_orthographic_projection_matrix(
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_observer_latitude_deg=0.0,
        sub_observer_longitude_deg_east=0.0,
    )

    assert incidence == pytest.approx(1.0)
    assert np.allclose(matrix, np.eye(2))


def test_local_orthographic_projection_matrix_foreshortens_toward_limb() -> None:
    matrix, incidence = local_orthographic_projection_matrix(
        center_latitude_deg=0.0,
        center_longitude_deg_east=0.0,
        sub_observer_latitude_deg=0.0,
        sub_observer_longitude_deg_east=60.0,
    )

    assert incidence == pytest.approx(0.5)
    assert matrix[0, 0] == pytest.approx(0.5)
    assert matrix[1, 1] == pytest.approx(1.0)
    assert matrix[0, 1] == pytest.approx(0.0)
    assert matrix[1, 0] == pytest.approx(0.0)


def test_apply_local_orthographic_projection_uses_inverse_sampling() -> None:
    image = np.tile(np.arange(9, dtype=np.float64), (9, 1))
    matrix = np.array([[0.5, 0.0], [0.0, 1.0]], dtype=np.float64)

    projected = apply_local_orthographic_projection(image, matrix)

    assert projected[4, 4] == pytest.approx(image[4, 4])
    assert projected[4, 6] == pytest.approx(image[4, 8])
