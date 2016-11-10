import os
import numpy as np
from bluesky.callbacks.core import CallbackBase


# supplementary functions
def _timestampstr(timestamp):
    """ convert timestamp to strftime formate """
    timestring = datetime.datetime.fromtimestamp(float(timestamp)).strftime(
        '%Y%m%d-%H%M%S')
    return timestring


class XpdAcqLiveTiffExporter(CallbackBase):
    """ Exporting tiff from given header(s).

    It is a variation of bluesky.callback.broker.LiveTiffExporter class
    It incorporate metadata and data from individual data points in
    the filenames.

    If also allow a room for dark subtraction if a valid dark_frame
    metdata scheme is taken

    Parameters
    ----------
    field : str
        a data key, e.g., 'image'
    root_dir : str
        top directory where tiff files will be saved
    template : str
        A templated for metadata that will be included in the file name.
        It is expressed with curly brackets, which will be filled in with
        the attributes of 'start', 'event', and (for image stacks) 'i',
        a sequential number.
        e.g., "scan{start.scan_id}_by_{start.experimenter}_{i}.tiff"
    data_fields : list, optional
        a list of strings for data fields want to be included. default
        is an empty list (not include any).
    base_template : str, optional
        template for base directory, default to None.
        It is expressed with curly brackets, which will be filled
        in with the attributes of 'start','event', (for image
        stacks) 'i', a sequential number. Files will be saved
        under root_dir/base_dir/. Example for base_dir_template
        could be "{start.sample_name}"
    save_dark : bool, optionl
        option to save dark frames, if True, subtracted images and dark
        images would be saved. default is False.
    dryrun : bool, optional
        default to False; if True, do not write any files
    overwrite : bool, optional
        default to False, raising an OSError if file exists
    db : Broker, optional
        The databroker instance to use, if not provided use databroker
        singleton

    Attributes
    ----------
    filenames : list of filenames written in ongoing or most recent run
    """

    def __init__(self, field, root_dir, template, data_fields=[],
                 base_dir=None, save_dark=False, dryrun=False,
                 overwrite=False, db=None):
        try:
            import tifffile
        except ImportError:
            print("Tifffile is required by this callback. Please install"
                  "tifffile and then try again."
                  "\n\n\tpip install tifffile\n\nor\n\n\tconda install "
                  "tifffile")
            raise
        else:
            # stash a reference so the module is accessible in self._save_image
            self._tifffile = tifffile

        if db is None:
            # Read-only db
            from databroker import DataBroker as db

        self.db = db

        # required args
        self.field = field
        self.root_dir = root_dir
        self.template = template
        # optioanal args 
        self.data_fields = data_fields  # list of keys for md to include
        self.base_template = base_template  # additional sub-folder
        self.save_dark = save_dark  # option of save dark 
        self.dryrun = dryrun
        self.overwrite = overwrite
        self.filenames = []
        self._start = None

    def _generate_filename(self, doc, is_imgstack):
        """ method to generate filename based on template

        It operates at event level
        """

        timestr = _timestampstr(doc['time'])
        # readback value for certain list of data keys
        data_val_list = []
        for key in self.data_fields:
            val = doc.get(key, None)
            if val is not None:
                data_val_list.append(val)
        data_val_trunk = '_'.join(data_val_list)
        # event sequence
        if is_imgstack:
            base_dir = self.base_template.format(start=self._start, event=doc)
            event_info = self.template.format(i=i, start=self._start,
                                              event=doc)
        else:
            base_dir = self.base_template.format(start=self._start, event=doc)
            event_info = self.template.format(start=self._start, event=doc)

        # total name
        filename = '_'.join(timestr, data_val_trunk, event_info)
        total_filename = os.path.join(self.root_dir,
                                      base_dir,
                                      filename)
        return total_filename

    def _save_image(self, image, filename):
        """ method to save image """
        fn_head, fn_tail = os.path.splitext(filename)
        if not os.path.isdir(fn_head):
            os.makedirs(fn_head, exist_ok=True)

        if not self.overwrite:
            if os.path.isfile(filename):
                raise OSError("There is already a file at {}. Delete "
                              "it and try again.".format(filename))
        if not self.dryrun:
            self._tifffile.imsave(filename, np.asarray(image))
            print("INFO: {} has been saved at {}"
                  .format(fn_head, fn_tail))

        self.filenames.append(filename)

    def start(self, doc):
        self.filenames = []
        # Convert doc from dict into dottable dict, more convenient
        # in Python format strings: doc.key == doc['key']
        self._start = doct.Document('start', doc)

        # find dark scan uid
        # TODO - make dark_md key flexible in the future
        if 'dark_frame' in doc:
            # found a dark header
            self.dark_uid = None
            self._is_dark = True
        elif 'dark_frame' in doc:
            if 'sc_dk_field_uid' in doc:
                self.dark_uid = doc['sc_dk_field_uid']
            else:
                print("INFO: No dark_frame was associated in this scan."
                      "no subtraction will be performed")
                self.dark_uid = None
            self._is_dark = False
        else:
            # left extra slot here for edgy case
            pass
        super().start(doc)

    def event(self, doc):
        """ tiff-saving operation applied at event level """
        if self.field not in doc['data']:
            raise KeyError('required field = {} is not in header'
                           .format(self.field))

        self.db.fill_event(doc)  # modifies in place
        image = np.asarray(doc['data'][self.field])

        # pull out dark image
        # note: intentionally leave it at event level, as we might have
        # dark frame per event
        if self.dark_uid is not None:
            # find dark image
            dark_header = self.db[self.dark_uid]
            dark_img = self.db.get_images(dark_header,
                                          self.field).squeeze()
        else:
            # no dark_uid -> make a dummy dark
            dark_img = np.zeros_like(image)
        image = (image - dark_img)
        if image.ndim == 2:
            filename = self._generate_filename(doc, False)
            self._save_image(image, filename)
            # if user wants wants raw dark
            if self.save_dark:
                self._save_image(dark_img, 'dark_'+filename)
        if image.ndim == 3:
            for i, plane in enumerate(image):
                filename = self._generate_filename(doc, True)
                self._save_image(plane, filename)
                # if user wants wants raw dark
                if self.save_dark:
                    self._save_image(dark_img, 'dark_'+filename)

    def stop(self, doc):
        # TODO: include sum logic in the future
        self._start = None
        self.filenames = []
        super().stop(doc)


# xpdAcq standard instantiation
root_dir = '/direct/XF28ID1/pe2_data/xpdUser/tiff_base/'
template = '{event.seq_num:03d}'
data_fields = ['temperature', 'diff_x', 'diff_y']
base_template = '{start.sample_name}'
xpdacq_tiff_export = XpdAcqLiveTiffExporter('pe1_image', root_dir,
                                            template, data_fields,
                                            base_template)
