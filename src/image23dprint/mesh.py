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

    def apply_mask(self, mask_img, axis='front', progress_callback=None):
        """
        Projects a 2D binary mask onto the 3D voxel grid and removes voxels
        outside the silhouette.

        Args:
            mask_img (np.ndarray): Binary mask image (0 or 255).
            axis (str): Projection axis ('front', 'side', or 'top').
            progress_callback (callable, optional): Progress callback function(current, total, message).
        """
        if progress_callback:
            progress_callback(0, 100, f"Processing {axis} mask...")

        # 1. Find bounding box of the non-zero area to ignore empty photo space
        coords = np.argwhere(mask_img)
        if coords.size == 0:
            if progress_callback:
                progress_callback(100, 100, f"{axis} mask is empty")
            return
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        idx = mask_img[y0:y1, x0:x1]
        # Ensure we have a 0-255 range for cv2.resize
        crop = (idx > 0).astype(np.uint8) * 255

        if progress_callback:
            progress_callback(30, 100, f"Resizing {axis} mask...")

        # 2. Map projection plane to (Z, X, Y) voxel indices
        if axis == 'front':
            ts = (self.shape[2], self.shape[0])  # (Z, X)
        elif axis == 'side':
            ts = (self.shape[2], self.shape[1])  # (Z, Y)
        else:
            ts = (self.shape[1], self.shape[0])  # (Y, X)

        # 3. Resize the core object silhouette to exactly fit the voxel plane
        resized = cv2.resize(crop, (ts[1], ts[0]), interpolation=cv2.INTER_NEAREST) > 127

        if progress_callback:
            progress_callback(50, 100, f"Carving voxels with {axis} mask...")

        if axis == 'front':
            m2d = resized[::-1, :].T # Flip Z for vertical alignment
            total_slices = self.shape[1]
            for y in range(total_slices):
                self.voxels[:, y, :] &= m2d
                if progress_callback and y % max(1, total_slices // 10) == 0:
                    pct = 50 + int((y / total_slices) * 50)
                    progress_callback(pct, 100, f"Carving {axis} slice {y+1}/{total_slices}...")
        elif axis == 'side':
            m2d = resized[::-1, :].T # Flip Z for vertical alignment
            total_slices = self.shape[0]
            for x in range(total_slices):
                self.voxels[x, :, :] &= m2d
                if progress_callback and x % max(1, total_slices // 10) == 0:
                    pct = 50 + int((x / total_slices) * 50)
                    progress_callback(pct, 100, f"Carving {axis} slice {x+1}/{total_slices}...")
        elif axis == 'top':
            m2d = resized.T # (X, Y)
            total_slices = self.shape[2]
            for z in range(total_slices):
                self.voxels[:, :, z] &= m2d
                if progress_callback and z % max(1, total_slices // 10) == 0:
                    pct = 50 + int((z / total_slices) * 50)
                    progress_callback(pct, 100, f"Carving {axis} slice {z+1}/{total_slices}...")

        if progress_callback:
            progress_callback(100, 100, f"{axis} mask applied")

    def generate_mesh(self, smooth=True, decimate=True, align_to_bed=True, progress_callback=None):
        """
        Extracts a 3D surface mesh from the voxel grid using Marching Cubes.

        Args:
            smooth (bool): Apply Laplacian smoothing to reduce voxel artifacts.
            decimate (bool): Reduce triangle count (simplify) for print efficiency.
            align_to_bed (bool): Translate the mesh so its bottom rests at Z=0.
            progress_callback (callable, optional): Progress callback function(current, total, message).

        Returns:
            trimesh.Trimesh: The generated 3D mesh object.
        """
        if not np.any(self.voxels):
            if progress_callback:
                progress_callback(100, 100, "No voxels to mesh")
            return None

        if progress_callback:
            progress_callback(0, 100, f"Generating mesh at resolution {self.shape}...")
        else:
            print(f"Generating mesh at resolution {self.shape}...")

        # Pad to ensure a watertight closed mesh at the boundaries
        padded = np.pad(self.voxels, 1, mode='constant', constant_values=0)

        if progress_callback:
            progress_callback(10, 100, "Running marching cubes algorithm...")

        verts, faces, normals, _ = measure.marching_cubes(padded, level=0.5)
        verts -= 1 # Compensate for padding shift

        if progress_callback:
            progress_callback(40, 100, f"Mesh extracted: {len(verts)} vertices, {len(faces)} faces")

        mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)

        current_progress = 40

        if smooth:
            if progress_callback:
                progress_callback(current_progress, 100, "Smoothing mesh...")
            mesh = trimesh.smoothing.filter_laplacian(mesh, iterations=10)
            current_progress = 60
            if progress_callback:
                progress_callback(current_progress, 100, "Smoothing complete")

        if decimate:
            if progress_callback:
                progress_callback(current_progress, 100, "Decimating mesh triangles...")
            else:
                print("Decimating mesh triangles...")
            mesh = mesh.simplify_quadric_decimation(face_count=len(mesh.faces)//5)
            current_progress = 80
            if progress_callback:
                progress_callback(current_progress, 100, f"Decimation complete: {len(mesh.faces)} faces")

        if align_to_bed:
            if progress_callback:
                progress_callback(current_progress, 100, "Aligning base to print bed (Z=0)...")
            else:
                print("Aligning base to print bed (Z=0)...")
            mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
            current_progress = 90

        if progress_callback:
            progress_callback(100, 100, f"Mesh complete: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

        return mesh

    def generate_thin_3d(self, mask_img, thickness_mm=2.0, scale_factor=1.0, progress_callback=None):
        """
        Generates a constant-thickness 3D mesh from a single 2D binary mask.
        (The '2D to Thin 3D' roadmap feature)

        Args:
            mask_img (np.ndarray): Binary mask image (True/False or 0/255).
            thickness_mm (float): The target extrusion thickness in real-world units.
            scale_factor (float): Pixels-to-mm conversion factor.
            progress_callback (callable, optional): Progress callback function(current, total, message).

        Returns:
            trimesh.Trimesh: The extruded 3D mesh.
        """
        if mask_img is None or not np.any(mask_img):
            if progress_callback:
                progress_callback(100, 100, "No mask to extrude")
            return None

        if progress_callback:
            progress_callback(0, 100, "Preparing mask for extrusion...")

        # 1. Clean mask and find contours
        m = (mask_img > 0).astype(np.uint8) * 255
        # Use simple extrusion via a voxel layer or direct trimesh creation
        # For 'Thin 3D', we can create a 2nd layer of the mask at a Z offset

        # Calculate voxel-space thickness
        vox_thickness = max(1, int(thickness_mm / scale_factor))

        if progress_callback:
            progress_callback(20, 100, f"Creating voxel grid ({thickness_mm}mm thick)...")

        # Create a temporary voxel grid for just this extrusion
        h, w = m.shape
        grid = np.zeros((w, vox_thickness, h), dtype=bool)

        # Resize mask to fit a reasonable grid if too large, but here we'll just use it
        # Actually, let's just use the mesh.apply_mask logic's style
        mask_resized = (m > 127).T # (W, H)
        for y in range(vox_thickness):
            grid[:, y, :] = mask_resized

        if progress_callback:
            progress_callback(40, 100, "Extracting mesh with marching cubes...")

        # extract mesh
        padded = np.pad(grid, 1, mode='constant', constant_values=0)
        verts, faces, normals, _ = measure.marching_cubes(padded, level=0.5)
        verts -= 1

        mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)

        if progress_callback:
            progress_callback(60, 100, "Applying real-world scaling...")

        # Apply real-world scaling
        # extents are [W, thickness, H] in voxel units
        mesh.apply_scale([scale_factor, scale_factor, scale_factor])

        if progress_callback:
            progress_callback(80, 100, "Rotating mesh for print orientation...")

        # Ensure base is at Z=0 (actually Y is the 'thickness' direction in our grid above)
        # But for STL export, customers usually want height to be Z.
        # Let's rotate it so it lies flat.
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0]))

        if progress_callback:
            progress_callback(100, 100, f"Thin 3D mesh complete: {len(mesh.vertices)} vertices")

        return mesh
