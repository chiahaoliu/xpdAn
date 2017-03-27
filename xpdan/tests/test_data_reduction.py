##############################################################################
#
# xpdan            by Billinge Group
#                   Simon J. L. Billinge sb2896@columbia.edu
#                   (c) 2016 trustees of Columbia University in the City of
#                        New York.
#                   All rights reserved
#
# File coded by:    Christopher J. Wright
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
##############################################################################
from itertools import product
from pprint import pprint

import numpy as np
import pytest

from xpdan.data_reduction import integrate_and_save, integrate_and_save_last, \
    save_tiff, save_last_tiff

integrate_params = ['dark_sub_bool',
                    'polarization_factor',
                    'mask_setting',
                    'mask_dict',
                    'save_image',
                    'config_dict', ]
good_kwargs = [(True, False), (.99,
                               # .95, .5
                               ),
               ('use_saved_mask_msk', 'use_saved_mask',
                'default', 'auto',
                'None',
                'array'),
               [None, {'alpha': 3}],
               (True, False), [None]]

bad_integrate_params = ['dark_sub_bool',
                        'polarization_factor',
                        'mask_setting',
                        'mask_dict',
                        'save_image',
                        'config_dict',
                        'sum_idx_list']

bad_kwargs = [['str'] for i in range(len(bad_integrate_params))]

integrate_kwarg_values = product(*good_kwargs)
integrate_kwargs = []
for vs in integrate_kwarg_values:
    d = {k: v for (k, v) in zip(integrate_params, vs)}
    integrate_kwargs.append((d, False))

for vs in bad_kwargs:
    d = {k: v for (k, v) in zip(bad_integrate_params, vs)}
    integrate_kwargs.append((d, True))

save_tiff_kwargs = []
save_tiff_params = ['dark_sub_bool', 'dryrun']
save_tiff_kwarg_values = [(True, False), (True, False)]

for vs in save_tiff_kwarg_values:
    d = {k: v for (k, v) in zip(save_tiff_params, vs)}
    save_tiff_kwargs.append((d, False))


@pytest.mark.parametrize(("kwargs", 'known_fail_bool'), integrate_kwargs)
def test_integrate_smoke(exp_db, tmp_dir, disk_mask, kwargs, known_fail_bool):
    if 'mask_setting' in kwargs.keys():
        if kwargs['mask_setting'] == 'use_saved_mask_msk':
            kwargs['mask_setting'] = disk_mask[0]
        elif kwargs['mask_setting'] == 'use_saved_mask':
            kwargs['mask_setting'] = disk_mask[1]
    elif 'mask_setting' in kwargs.keys() and kwargs['mask_setting'] == 'array':
        kwargs['mask_setting'] = np.random.random_integers(
            0, 1, disk_mask[-1].shape).astype(bool)
    kwargs['db'] = exp_db
    kwargs['save_dir'] = tmp_dir
    pprint(kwargs)
    a = integrate_and_save(exp_db[-1], **kwargs)
    b = integrate_and_save_last(**kwargs)
    if known_fail_bool and not a and not b:
        pytest.xfail('Bad params')


@pytest.mark.parametrize(("kwargs", 'known_fail_bool'), save_tiff_kwargs)
def test_save_tiff_smoke(exp_db, tmp_dir, kwargs, known_fail_bool):
    kwargs['db'] = exp_db
    kwargs['save_dir'] = tmp_dir
    pprint(kwargs)
    a = save_tiff(exp_db[-1], **kwargs)
    b = save_last_tiff(**kwargs)
    if known_fail_bool and not a and not b:
        pytest.xfail('Bad params')
