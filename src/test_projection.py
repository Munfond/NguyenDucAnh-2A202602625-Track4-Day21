"""CP2 numeric checks. Run from repo root: python -m src.test_projection.

The four-point reference case comes from the supplied CP2 lab instructions.
"""
import numpy as np

from starter.datasets import load_frame
from starter.projection import cam_to_image, project_velo_to_image, velo_to_cam


def main():
    np.set_printoptions(suppress=True, precision=2)
    fr = load_frame("data/synthetic", "000000")
    pts = np.array([[10., 0., 0.], [np.nan, 0., 0.],
                    [-10., 0., 0.], [10., 50., 0.]])
    cam = velo_to_cam(pts, fr["calib"])
    uv, depth, mask = cam_to_image(cam, fr["calib"].P2, fr["image"].shape)
    print("camera frame:\n", cam)
    print("uv:", uv, "depth:", depth, "mask:", mask)
    assert cam.shape == (4, 3)
    assert abs(cam[0, 2] - 9.73) < .01
    assert mask.tolist() == [True, False, False, False]
    assert uv.shape == (1, 2) and depth.shape == (1,)
    assert np.allclose(uv[0], [614, 175], atol=1)

    # Non-square image and exact boundaries catch H/W swaps and inclusive bounds.
    P = np.array([[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.]])
    edge_pts = np.array([[0., 0., 1.], [19., 9., 1.], [20., 0., 1.],
                         [0., 10., 1.], [-1., 0., 1.], [0., 0., 0.],
                         [0., 0., .1], [np.inf, 0., 1.]])
    with np.errstate(divide="raise", invalid="raise"):
        uv, depth, mask = cam_to_image(edge_pts, P, (10, 20, 3))
        assert mask.tolist() == [True, True, False, False, False, False, False, False]
        assert np.array_equal(uv, [[0., 0.], [19., 9.]])
        assert np.array_equal(depth, [1., 1.])
        uv, depth, mask = cam_to_image(np.empty((0, 3)), P, (10, 20, 3))
        assert uv.shape == (0, 2) and depth.shape == mask.shape == (0,)
        zero_denominator = P.copy()
        zero_denominator[2] = 0
        uv, depth, mask = cam_to_image(edge_pts[:2], zero_denominator, (10, 20, 3))
        assert not mask.any() and uv.shape == (0, 2)

    for root, fid, expected in [("data/synthetic", "000000", 3910),
                                ("data/kitti_mini", "000011", 19946),
                                ("data/nuscenes_mini_subset", "scene-0103_010", 3120)]:
        frame = load_frame(root, fid)
        _, _, valid = project_velo_to_image(frame["points"], frame["calib"], frame["image"].shape)
        assert valid.sum() == expected, (root, int(valid.sum()), expected)
        print(f"{root}/{fid}: inside_image={valid.sum()} [PASS]")
    print("CP2 self-test passed")


if __name__ == "__main__":
    main()
