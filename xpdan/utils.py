import os
import datetime
import numpy as np
import yaml
from mock import MagicMock

# HOTFIX at beamline
#from bluesky import RunEngine
#from bluesky.examples import Reader, motor
#from bluesky.plans import scan, count, relative_scan

from databroker import Broker 

from .glbl import an_glbl


def _clean_info(input_str):
    return input_str.strip().replace(' ', '_')


def _timestampstr(timestamp):
    """ convert timestamp to strftime formate """
    timestring = datetime.datetime.fromtimestamp(float(timestamp)).strftime(
        '%Y%m%d-%H%M')
    return timestring


def start_xpdan():
    """ function to read in beamtime info and initialize analysis
    environment

    Note
    ----
    Temperary version
    """

    bt_fn =os.path.join(an_glbl.config_base, 'bt_bt.yml')
    if os.path.isfile(bt_fn):
        with open(bt_fn, 'r') as f:
            an = yaml.load(f)
    else:
        print("INFO: have you started a beamtime yet?")
        print("Please contact beamline scientist for help")
        return

"""
# area det for simulation
class SimulatedPE1C(Reader):

    def __init__(self, name, read_fields):
        self.images_per_set = MagicMock()
        self.images_per_set.get = MagicMock(return_value=5)
        self.number_of_sets = MagicMock()
        self.number_of_sets.put = MagicMock(return_value=1)
        self.number_of_sets.get = MagicMock(return_value=1)
        self.cam = MagicMock()
        self.cam.acquire_time = MagicMock()
        self.cam.acquire_time.put = MagicMock(return_value=0.1)
        self.cam.acquire_time.get = MagicMock(return_value=0.1)
        self._staged = False

        super().__init__(name, read_fields)

        self.ready = True  # work around a hack in Reader

    def stage(self):
        if self._staged:
            raise RuntimeError("Device is already staged.")
        self._staged = True
        return [self]

    def unstage(self):
        self._staged = False


def _generate_simulation_data():
    if os.environ['XPDAN_SETUP'] != str(2):
        raise RuntimeError("ONLY insert data if you are running"
                           "simulation")
    # simulated det
    pe1c = SimulatedPE1C('pe1c',
                         {'pe1_image': lambda: np.random.randn(25, 25)})
    # TODO : add md schema later
    RE = RunEngine({})
    RE.subscribe('all', an_glbl.exp_db.mds.insert)
    RE(count([pe1c]))
    RE(scan([pe1c], motor, 1, 5, 5))
    RE(scan([pe1c], motor, 1, 10, 10))

"""
