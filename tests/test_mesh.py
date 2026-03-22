import numpy as np
from image23dprint.mesh import SpaceCarver

def test_space_carver_cube():
    # A 32x32x32 carving with all-white masks should yield a cube
    carver = SpaceCarver(res=32)
    mask = np.ones((32, 32), dtype=np.uint8) * 255
    
    carver.apply_mask(mask, axis='front')
    carver.apply_mask(mask, axis='side')
    carver.apply_mask(mask, axis='top')
    
    assert np.all(carver.voxels)
    
    mesh = carver.generate_mesh()
    assert mesh is not None
    # For a cube, it should be manifold
    assert mesh.is_watertight

def test_space_carver_sphere_hole():
    # Carve a hole in the middle
    carver = SpaceCarver(res=32)
    mask = np.ones((32, 32), dtype=np.uint8) * 255
    # Mask out the middle
    mask[10:22, 10:22] = 0
    
    carver.apply_mask(mask, axis='front')
    # The middle voxels should be False
    assert not carver.voxels[16, 16, 16]
