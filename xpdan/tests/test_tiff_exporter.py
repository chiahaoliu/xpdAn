import os
import tempfile
from tifffile import imread
from xpdan.tests.conftest import img_size
from xpdan.callbacks_core import XpdAcqLiveTiffExporter

# standard config
base = tempfile.mkdtemp()
template = os.path.join(base, 'xpdUser/tiff_base/')
data_fields = ['temperature', 'diff_x', 'diff_y', 'eurotherm'] # known devices

def test_tiff_export(exp_db):
    tif_export = XpdAcqLiveTiffExporter('pe1_image', template, data_fields,
                                        overwrite=True, db=exp_db)
    exp_db.process(exp_db[-1], tif_export)
    # make sure files are sasved
    for fn in tif_export.filenames:
        assert os.path.isfile(fn)
    # confirm image is the same as input
    for fn in tif_export.filenames:
        img = imread(fn)
        assert img.shape == next(img_size)
        # logic defined in insert_img. after successful dark_sub array==0
        # TODO: update this logic when we are ready for
        # fs-integrated-Reader
        assert np.all(img == 0)
