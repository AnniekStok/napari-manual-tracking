import math
import numpy                        as np
import pandas                       as pd
import scipy.ndimage                as spim
from typing                         import List
from skimage                        import measure
from skimage.morphology             import ball
from porespy.metrics._regionprops   import RegionPropertiesPS


class ExtendedRegionProperties(RegionPropertiesPS):
    """Adding additional properties to skimage.measure._regionprops following the logic from the porespy package with some modifications to include the spacing information."""

    @property
    def non_calibrated_centroid(self):
        return tuple(self.coords.mean(axis=0))
    
    @property
    def axes(self):
        """Calculate the three axes radii"""
        cell        = np.where(self._label_image == self.label) # np.where returns a tuple of all the indices in the different dimensions z,y,x that fulfill the condition. The indices in z are different than in y, but the length is the same.
        voxel_count = len(cell[0]) 

        z, y, x     = cell

        # finding the center z,y,x and calibrate
        z = (z - np.mean(z)) * self._spacing[0]
        y = (y - np.mean(y)) * self._spacing[1]
        x = (x - np.mean(x)) * self._spacing[2]

        
        i_xx    = np.sum(y ** 2 + z ** 2)
        i_yy    = np.sum(x ** 2 + z ** 2)
        i_zz    = np.sum(x ** 2 + y ** 2) # Moments of inertia with respect to the x, y, z, axis. 
        i_xy    = np.sum(x * y)
        i_xz    = np.sum(x * z)
        i_yz    = np.sum(y * z) # Products of inertia. A measure of imbalance in the mass distribution. 

        i       = np.array([[i_xx, -i_xy, -i_xz], [-i_xy, i_yy, -i_yz], [-i_xz, -i_yz, i_zz]]) # Tensor of inertia. For calculating the Principal Axes of Inertia (eigvec & eigval).  
        eig     = np.linalg.eig(i)

        eigval  = eig[0]

        longaxis  = np.where(np.min(eigval) == eigval)[0][0]
        shortaxis = np.where(np.max(eigval) == eigval)[0][0]
        midaxis   = 0 if shortaxis != 0 and longaxis != 0 else 1 if shortaxis != 1 and longaxis != 1 else 2

        # Calculate 3 radii (or 3 principal axis lengths of the fitted ellipsoid.) 
        longr     = math.sqrt(5.0 / 2.0 * (eigval[midaxis]   + eigval[shortaxis] - eigval[longaxis])  / voxel_count)
        midr      = math.sqrt(5.0 / 2.0 * (eigval[shortaxis] + eigval[longaxis]  - eigval[midaxis])   / voxel_count)
        shortr    = math.sqrt(5.0 / 2.0 * (eigval[longaxis]  + eigval[midaxis]   - eigval[shortaxis]) / voxel_count)
        return (shortr, midr, longr) # return calibrated three axis radii
    
    @property
    def eccentricity(self):
        """Calculate the eccentricity based on the shortest and longest axes of the cell"""

        shortest_axis_length = self.axes[0] * 2
        longest_axis_length = self.axes[2] * 2
        return math.sqrt(1 - (shortest_axis_length**2) / (longest_axis_length**2))

    @property
    def surface_area(self):
        verts, faces, _, _ = measure.marching_cubes(self._label_image == self.label, level=0.5, spacing=self._spacing)
        surface_area = measure.mesh_surface_area(verts, faces)
        return surface_area

    @property
    def surface_area_smooth(self):
        mask = self.mask
        tmp = np.pad(np.atleast_3d(mask), pad_width=1, mode='constant')
        kernel_radii = np.array(self._spacing)
        tmp = spim.convolve(tmp, weights=ball(min(kernel_radii))) / 5  # adjust kernel size for anisotropy
        verts, faces, _, _ = measure.marching_cubes(volume=tmp, level=0, spacing = self._spacing)
        area = measure.mesh_surface_area(verts, faces)
        return area

    @property
    def volume(self):
        vol = np.sum(self._label_image == self.label) * np.prod(self._spacing)
        return vol

    @property
    def voxel_count(self):
        voxel_count = np.sum(self._label_image == self.label)
        return voxel_count

def regionprops_extended(img, voxel_size) -> List[ExtendedRegionProperties]:
    """Create instance of ExtendedRegionProperties that extends skimage.measure.RegionProperties"""

    results = measure.regionprops(img, spacing = voxel_size)
    for i, _ in enumerate(results):
        a = results[i]
        b = ExtendedRegionProperties(slice = a.slice,
                            label = a.label,
                            label_image = a._label_image,
                            intensity_image = a._intensity_image,
                            cache_active = a._cache_active,
                            spacing = a._spacing)
        results[i] = b

    return results

def props_to_dataframe(regionprops, selected_properties = None) -> pd.DataFrame:
    """Convert ExtendedRegionProperties instance to pandas dataframe, following the logical from porespy.metrics._regionprops.props_to_dataframe"""

    if selected_properties is None:
        selected_properties = regionprops[0].__dict__()
  
    new_props = ['label']
    # need to check if any of the props return multiple values
    for item in selected_properties:
        if isinstance(getattr(regionprops[0], item), tuple):
            for i, subitem in enumerate(getattr(regionprops[0], item)):
                new_props.append(item + '-' + str(i+1))
        else:
            new_props.append(item)

    # get the measurements for all properties of interest
    d = {}
    for k in new_props:
        if '-' in k:
            # If property is a tuple, extract the tuple element
            prop_name, idx = k.split('-')
            idx = int(idx) - 1
            d[k] = np.array([getattr(r, prop_name)[idx] for r in regionprops])
        else:
            d[k] = np.array([getattr(r, k) for r in regionprops])

    # Create pandas data frame an return
    df = pd.DataFrame(d)

    column_naming = {
    'centroid-1'         : 'z [um]',
    'centroid-2'         : 'y [um]',
    'centroid-3'         : 'x [um]',
    'non_calibrated_centroid-1': 'z',
    'non_calibrated_centroid-2': 'y',
    'non_calibrated_centroid-3': 'x',
    'voxel_count'        : 'voxel count',
    'volume'             : 'volume [um^3]',
    'sphericity'         : 'sphericity',
    'surface_area'       : 'surface area (marching cubes) [um^2]',
    'surface_area_smooth': 'surface area (marching cubes, smoothed) [um^2]'
    }

    df = df.rename(columns = column_naming)

    return df

def calculate_extended_props(image, properties, voxel_size) -> pd.DataFrame:
    """Create regionproperties, and convert to pandas dataframe"""
    
    props = regionprops_extended(image, voxel_size)
    if len(props) > 0:
        df = props_to_dataframe(props, properties)
    else:
        df = pd.DataFrame()
    return df
