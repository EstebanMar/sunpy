# -*- coding: utf-8 -*-
#
#
# <License info will go here...>
"""
    Provides programs to process and analyze RHESSI data.

    .. warning:: This module is still in development!

"""

from __future__ import absolute_import
import numpy as np
import pyfits
import sunpy

# Measured fixed grid parameters
grid_pitch = (4.52467, 7.85160, 13.5751, 23.5542, 40.7241, 70.5309, 122.164, 
              211.609, 366.646)
grid_orientation = (3.53547, 2.75007, 3.53569, 2.74962, 3.92596, 2.35647, 
                    0.786083, 0.00140674, 1.57147)

data_servers = ('http://hesperia.gsfc.nasa.gov/hessidata/', 
                'http://hessi.ssl.berkeley.edu/hessidata/',
                'http://soleil.i4ds.ch/hessidata/')

def get_obssumm_file(time_range):
    """Download the RHESSI observing summary data from one of the RHESSI 
    servers. 
    
    Parameters
    ----------
    time_range : A TimeRange or time range compatible string

    Returns
    -------
    value : tuple
        Return a tuple (filename, headers) where filename is the local file 
        name under which the object can be found, and headers is 
        whatever the info() method of the object returned by urlopen.

    See Also
    --------

    Examples
    --------
    >>> import sunpy.instr.rhessi as rhessi
    >>> rhessi.get_obssumm_file(('2011/04/04', '2011/04/05'))
    
    Reference
    ---------
    | 
    
    .. note:: This API is currently limited to providing data from 
    whole days only.

    """
    
    _time_range = TimeRange(time_range)
    
    #TODO need to check which is the closest servers
    url_root = data_servers[0]
    
    url = url_root + _time_range.t1.strftime("%Y/%m/%d")
    print('Downloading file: ' + url)
    #f = urllib.urlretrieve(url)

    #return f


def _backproject(calibrated_event_list, detector=8, pixel_size=(1.,1.), image_dim=(64,64)):
    """Given a stacked calibrated event list fits file create a back 
    projection image for an individual detectors. This function is used by
    backprojection.
    
    Parameters
    ----------
    calibrated_event_list : string
        filename of a RHESSI calibrated event list
    
    detector : int
        the detector number
        
    pixel_size : 2-tuple
        the size of the pixels in arcseconds. Default is (1,1).
        
    image_dim : 2-tuple
        the size of the output image in number of pixels
        
    Returns
    -------
    image : ndarray
        Return a backprojection image.

    See Also
    --------

    Examples
    --------
    >>> import sunpy.instr.rhessi as rhessi
    >>> image = rhessi.get_latest_l0cs_goes_data(sunpy.RHESSI_EVENT_LIST, detector = 3)
    
    Reference
    ---------
    | 

    """
    fits = pyfits.open(calibrated_event_list)
    info_parameters = fits[2]
    
    detector_efficiency = info_parameters.data.field('cbe_det_eff$$REL')    
    fits = pyfits.open(calibrated_event_list)

    fits_detector_index = detector + 2
    detector_index = detector - 1
    grid_angle = np.pi/2. - grid_orientation[detector_index]
    harm_ang_pitch = grid_pitch[detector_index]/1

    phase_map_center = fits[fits_detector_index].data.field('phase_map_ctr')
    this_roll_angle = fits[fits_detector_index].data.field('roll_angle')
    modamp = fits[fits_detector_index].data.field('modamp')
    grid_transmission = fits[fits_detector_index].data.field('gridtran')
    count = fits[fits_detector_index].data.field('count')

    tempa = (np.arange(image_dim[0]*image_dim[1]) %  image_dim[0]) - (image_dim[0]-1)/2.
    tempb = tempa.reshape(image_dim[0],image_dim[1]).transpose().reshape(image_dim[0]*image_dim[1])

    pixel = np.array(zip(tempa,tempb))*pixel_size[0]
    phase_pixel = (2*np.pi/harm_ang_pitch)* ( np.outer(pixel[:,0], np.cos(this_roll_angle - grid_angle)) - 
                                              np.outer(pixel[:,1], np.sin(this_roll_angle - grid_angle))) + phase_map_center
    phase_modulation = np.cos(phase_pixel)    
    gridmod = modamp * grid_transmission
    probability_of_transmission = gridmod*phase_modulation + grid_transmission
    bproj_image = np.inner(probability_of_transmission, count).reshape(image_dim)
        
    return bproj_image

def backprojection(calibrated_event_list, pixel_size=(1.,1.), image_dim=(64,64)):
    """Given a stacked calibrated event list fits file create a back 
    projection image.
    
    .. warning:: The image is not in the right orientation!

    Parameters
    ----------
    calibrated_event_list : string
        filename of a RHESSI calibrated event list
    
    detector : int
        the detector number
        
    pixel_size : 2-tuple
        the size of the pixels in arcseconds. Default is (1,1).
        
    image_dim : 2-tuple
        the size of the output image in number of pixels
        
    Returns
    -------
    map : RHESSImap
        Return a backprojection map.

    See Also
    --------

    Examples
    --------
    >>> import sunpy.instr.rhessi as rhessi
    >>> map = rhessi.backprojection(sunpy.RHESSI_EVENT_LIST)
    >>> map.show()
    
    Reference
    ---------
    | 

    """
    import sunpy.sun.constants as sun
    from sunpy.sun.sun import angular_size
    from sunpy.sun.sun import sunearth_distance
    from sunpy.time import TimeRange
    
    calibrated_event_list = sunpy.RHESSI_EVENT_LIST
    fits = pyfits.open(calibrated_event_list)
    info_parameters = fits[2]
    xyoffset = info_parameters.data.field('USED_XYOFFSET')[0]
    time_range = TimeRange(info_parameters.data.field('ABSOLUTE_TIME_RANGE')[0])
    
    image = np.zeros(image_dim)
    
    #find out what detectors were used
    det_index_mask = fits[1].data.field('det_index_mask')[0]    
    detector_list = (np.arange(9)+1) * np.array(det_index_mask)
    for detector in detector_list:
        if detector > 0:
            image = image + _backproject(calibrated_event_list, detector=detector, pixel_size=pixel_size, image_dim=image_dim)
    
    dict_header = {
        "DATE-OBS": time_range.center().strftime("%Y-%m-%d %H:%M:%S"), 
        "CDELT1": pixel_size[0],
        "NAXIS1": image_dim[0],
        "CRVAL1": xyoffset[0],
        "CRPIX1": image_dim[0]/2 + 0.5, 
        "CUNIT1": "arcsec",
        "CTYPE1": "HPLN-TAN",
        "CDELT2": pixel_size[1],
        "NAXIS2": image_dim[1],
        "CRVAL2": xyoffset[1],
        "CRPIX2": image_dim[0]/2 + 0.5,
        "CUNIT2": "arcsec",
        "CTYPE2": "HPLT-TAN",
        "HGLT_OBS": 0,
        "HGLN_OBS": 0,
        "RSUN_OBS": angular_size(time_range.center()),
        "RSUN_REF": sun.radius,
        "DSUN_OBS": sunearth_distance(time_range.center()) * sunpy.sun.constants.au
    }
    
    header = sunpy.map.MapHeader(dict_header)
    result_map = sunpy.map.BaseMap(image, header)
            
    return result_map