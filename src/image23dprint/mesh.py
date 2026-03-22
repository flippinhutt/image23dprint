import numpy as np
from skimage import measure
import trimesh
import cv2

class SpaceCarver:
    """
    Core engine for 3D reconstruction using Space Carving (Voxel Carving).
    Consumes multiple 2D binary masks (Front, Side, Top) to iteratively 'carve' 
    a 3D voxel grid into the shape of the physical object.
    """
    
    def __init__(self, res=128, dims=(1, 1, 1)):
        """
        Initialize the voxel grid with target proportions.
        
        Args:
            res (int): The resolution of the longest dimension.
            dims (tuple): Target real-world dimensions (Width, Depth, Height).
        """
        self.res = res
        max_d = max(dims)
        # Calculate voxel counts per dimension to match real-world aspect ratio
        self.shape = (int(res * dims[0]/max_d), int(res * dims[1]/max_d), int(res * dims[2]/max_d))
        self.shape = tuple(max(4, s) for s in self.shape)
        self.voxels = np.ones(self.shape, dtype=bool)

    def apply_mask(self, mask_img, axis='front'):
        """
        Projects a 2D binary mask onto the 3D voxel grid and removes voxels 
        outside the silhouette.
        
        Args:
            mask_img (np.ndarray): Binary mask image (0 or 255).
            axis (str): Projection axis ('front', 'side', or 'top').
        """
        # 1. Find bounding box of the non-zero area to ignore empty photo space
        coords = np.argwhere(mask_img)
        if coords.size == 0:
            return
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        idx = mask_img[y0:y1, x0:x1]
        # Ensure we have a 0-255 range for cv2.resize
        crop = (idx > 0).astype(np.uint8) * 255

        # 2. Map projection plane to (Z, X, Y) voxel indices
        if axis == 'front':
            ts = (self.shape[2], self.shape[0])  # (Z, X)
        elif axis == 'side':
            ts = (self.shape[2], self.shape[1])  # (Z, Y)
        else:
            ts = (self.shape[1], self.shape[0])  # (Y, X)

        # 3. Resize the core object silhouette to exactly fit the voxel plane
        resized = cv2.resize(crop, (ts[1], ts[0]), interpolation=cv2.INTER_NEAREST) > 127
        
        if axis == 'front':
            m2d = resized[::-1, :].T # Flip Z for vertical alignment
            for y in range(self.shape[1]):
                self.voxels[:, y, :] &= m2d
        elif axis == 'side':
            m2d = resized[::-1, :].T # Flip Z for vertical alignment
            for x in range(self.shape[0]):
                self.voxels[x, :, :] &= m2d
        elif axis == 'top':
            m2d = resized.T # (X, Y)
            for z in range(self.shape[2]):
                self.voxels[:, :, z] &= m2d

    def generate_mesh(self, smooth=True, decimate=True, align_to_bed=True):
        """
        Extracts a 3D surface mesh from the voxel grid using Marching Cubes.
        
        Args:
            smooth (bool): Apply Laplacian smoothing to reduce voxel artifacts.
            decimate (bool): Reduce triangle count (simplify) for print efficiency.
            align_to_bed (bool): Translate the mesh so its bottom rests at Z=0.
            
        Returns:
            trimesh.Trimesh: The generated 3D mesh object.
        """
        if not np.any(self.voxels):
            return None
        
        print(f"Generating mesh at resolution {self.shape}...")
        # Pad to ensure a watertight closed mesh at the boundaries
        padded = np.pad(self.voxels, 1, mode='constant', constant_values=0)
        verts, faces, normals, _ = measure.marching_cubes(padded, level=0.5)
        verts -= 1 # Compensate for padding shift
        
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)
        
        if smooth:
            mesh = trimesh.smoothing.filter_laplacian(mesh, iterations=10)
            
        if decimate:
            print("Decimating mesh triangles...")
            mesh = mesh.simplify_quadric_decimation(face_count=len(mesh.faces)//5)
            
        if align_to_bed:
            print("Aligning base to print bed (Z=0)...")
            mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
            
        return mesh

    def generate_thin_3d(self, mask_img, thickness_mm=2.0, scale_factor=1.0):
        """
        Generates a constant-thickness 3D mesh from a single 2D binary mask.
        (The '2D to Thin 3D' roadmap feature)

        Args:
            mask_img (np.ndarray): Binary mask image (True/False or 0/255).
            thickness_mm (float): The target extrusion thickness in real-world units.
            scale_factor (float): Pixels-to-mm conversion factor.

        Returns:
            trimesh.Trimesh: The extruded 3D mesh.
        """
        if mask_img is None or not np.any(mask_img):
            return None

        # 1. Clean mask and find contours
        m = (mask_img > 0).astype(np.uint8) * 255
        # Use simple extrusion via a voxel layer or direct trimesh creation
        # For 'Thin 3D', we can create a 2nd layer of the mask at a Z offset
        
        # Calculate voxel-space thickness
        vox_thickness = max(1, int(thickness_mm / scale_factor))
        
        # Create a temporary voxel grid for just this extrusion
        h, w = m.shape
        grid = np.zeros((w, vox_thickness, h), dtype=bool)
        
        # Resize mask to fit a reasonable grid if too large, but here we'll just use it
        # Actually, let's just use the mesh.apply_mask logic's style
        mask_resized = (m > 127).T # (W, H)
        for y in range(vox_thickness):
            grid[:, y, :] = mask_resized
            
        # extract mesh
        padded = np.pad(grid, 1, mode='constant', constant_values=0)
        verts, faces, normals, _ = measure.marching_cubes(padded, level=0.5)
        verts -= 1
        
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)
        
        # Apply real-world scaling
        # extents are [W, thickness, H] in voxel units
        mesh.apply_scale([scale_factor, scale_factor, scale_factor])
        
        # Ensure base is at Z=0 (actually Y is the 'thickness' direction in our grid above)
        # But for STL export, customers usually want height to be Z.
        # Let's rotate it so it lies flat.
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0]))
        
        return mesh
