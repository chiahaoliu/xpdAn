#!/usr/bin/env python
##############################################################################
#
# xpdacq            by Billinge Group
#                   Simon J. L. Billinge sb2896@columbia.edu
#                   (c) 2016 trustees of Columbia University in the City of
#                        New York.
#                   All rights reserved
#
# File coded by:    Timothy Liu
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
##############################################################################
import os
import time

import yaml

# FIXME: It seems pyFAI upstream master has started deprecating
# calibartion. Need solution for pyFAI 0.16.0
import pyFAI
from pyFAI.calibration import Calibration, PeakPicker, Calibrant
from pyFAI.gui.utils import update_fig
from pyFAI.calibrant import get_calibrant
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator

from xpdan.dev_utils import _timestampstr
from tempfile import TemporaryDirectory


def _save_calib_param(calib_c, timestr, calib_yml_fp):
    """save calibration parameters to designated location

    Parameters
    ----------
    calib_c : pyFAI.calibration.Calibration instance
        pyFAI Calibration instance with parameters after calibration
    time_str : str
        human readable time string
    calib_yml_fp : str
        filepath to the yml file which stores calibration param
    """
    # save glbl attribute for xpdAcq
    timestr = _timestampstr(time.time())
    calibrant_name = calib_c.calibrant.__repr__().split(' ')[0]
    calib_config_dict = {}
    calib_config_dict = calib_c.geoRef.getPyFAI()
    calib_config_dict.update(calib_c.geoRef.getFit2D())
    calib_config_dict.update({'poni_file_name':
                              calib_c.basename + '.poni'})
    calib_config_dict.update({'time': timestr})
    calib_config_dict.update({'dSpacing':
                              calib_c.calibrant.dSpacing})
    calib_config_dict.update({'calibrant_name':
                              calibrant_name})

    # save yaml dict used for xpdAcq
    with open(os.path.expanduser(calib_yml_fp), 'w') as f:
        yaml.dump(calib_config_dict, f)
    stem, fn = os.path.split(calib_yml_fp)
    print("INFO: End of calibration process. This set of calibration "
          "will be injected as metadata to subsequent scans until you "
          "perform this process again\n")
    print("INFO: you can also use:\n>>> show_calib()\ncommand to check"
          " current calibration parameters")
    return calib_config_dict


def img_calibration(img, wavelength, calibrant=None, detector=None,
                    interactive=True, calib_ref_fp=None,
                    calib_kwargs=None):
    """function to calibrate experimental geometry wrt an image

    Parameters
    ----------
    img : ndarray
        2D powder diffraction image from calibrant
    wavelength : float
        x-ray wavelength in angstrom.
    calibrant : str, optional
        calibrant being used, default is 'Ni'.
        input could be ``full file path'' to customized d-spacing file with
        ".D" extension or one of pre-defined calibrant names.
        List of pre-defined calibrant names is:
        ['NaCl', 'AgBh', 'quartz', 'Si_SRM640', 'Ni', 'Si_SRM640d',
         'Si_SRM640a', 'alpha_Al2O3', 'LaB6_SRM660b', 'TiO2', 'CrOx',
         'LaB6_SRM660c', 'CeO2', 'Si_SRM640c', 'CuO', 'Si_SRM640e',
         'PBBA', 'ZnO', 'Si', 'C14H30O', 'cristobaltite', 'LaB6_SRM660a',
         'Au', 'Cr2O3', 'Si_SRM640b', 'LaB6', 'Al', 'mock']
    detector : str or pyFAI.detector.Detector instance, optional.
        detector used to collect data. default value is 'perkin-elmer'.
        other allowed values are in pyFAI documentation.
    calib_ref_fp : str, optional
        full file path to where the native pyFAI calibration information
        will be saved. Default to ``/tmp`` directory.
    calib_kwargs:
        Additional keyword argument for pyFAI.calibration.PeakPicker.
        Please refer to pyFAI documentation for full options.

    Returns
    -------
    ai : pyFAI.AzimuthalIntegrator
        instance of AzimuthalIntegrator. can be used to integrate 2D
        images directly.
    Examples
    --------
    # calib Ni image with pyFAI default ``Ni.D`` d-spacing
    # with wavlength 0.1823 angstrom
    >>> import tifffile as tif
    >>> ni_img = tif.imread(<path_to_img_file>)
    >>> ai = img_calibration(ni_img, 0.1823)

    # calib Ni image with pyFAI customized ``myNi.D`` d-spacing
    # with wavlength 0.1823 angstrom
    >>> import tifffile as tif
    >>> ni_img = tif.imread(<path_to_img_file>)
    >>> ai = img_calibration(ni_img, 0.1823, 'path/to/myNi.D')

    # integrate image right after calibration
    >>> import matplotlib.pyplot as plt
    >>> npt = 1482 # just a number for demonstration
    >>> q, Iq = ai.integrate1d(ni_img, npt, unit="q_nm^-1")
    >>> plt.plot(q, Iq)

    Reference
    ---------
    pyFAI documentation:
    http://pyfai.readthedocs.io/en/latest/
    """
    # default args : initial value for pyFAI calibration. It doesn't affect
    # calibration results.
    dist = 0.1  #mm


    # vendoring pyFAI ``calib`` function
    wavelength *= 10**-10
    if detector is None:
        detector = pyFAI.detectors.Perkin() 
    if calibrant is None:
        calibrant = get_calibrant('Ni')
    elif isinstance(calibrant, list):
        calibrant = Calibrant(dSpacing=calibrant)
    calibrant.set_wavelength(wavelength)
    assert calibrant.get_dSpacing()
    # FIXME: It seems pyFAI upstream master has started deprecating
    # calibartion with their own gui...Need solution for pyFAI 0.16.0
    # configure calibration instance
    c = Calibration(calibrant=calibrant, detector=detector,
                    wavelength=wavelength)
    c.gui = interactive
    # annoying pyFAI logic, you need valid fn to start calibration
    _is_tmp_dir = False
    if calib_ref_fp is None:
        _is_tmp_dir = True
        td = TemporaryDirectory()
        calib_ref_fp = os.path.join(td.name, 'from_calib_func')
    basename, ext = os.path.splitext(calib_ref_fp)
    c.basename = basename
    c.pointfile = basename + ".npt"
    c.ai = AzimuthalIntegrator(dist=dist, detector=detector,
                               wavelength=calibrant.wavelength)
    if calib_kwargs is None:
        calib_kwargs = {}
    c.peakPicker = PeakPicker(img, reconst=True,
                              pointfile=c.pointfile,
                              calibrant=calibrant,
                              wavelength=calibrant.wavelength,
                              **calib_kwargs)
    if interactive:
        c.peakPicker.gui(log=True, maximize=True, pick=True)
        update_fig(c.peakPicker.fig)
    c.gui_peakPicker()
    c.ai.setPyFAI(**c.geoRef.getPyFAI())
    c.ai.wavelength = c.geoRef.wavelength
    if _is_tmp_dir:
        td.cleanup()

    # img2 = img.copy()
    # img2 /= calib_c.ai.polarization(img2.shape, .99)
    # calib_c, timestr = _calibration(img2, c, calib_ref_fp, **kwargs)

    return c, c.ai
