import os

from bluesky.callbacks.broker import LiveImage
from shed.translation import FromEventStream, ToEventStream
from skbeam.io import save_output
from skbeam.io.fit2d import fit2d_save
from tifffile import imsave

from xpdan.db_utils import query_background, query_dark, temporal_prox
from xpdan.formatters import render, clean_template
from xpdan.io import pdf_saver, dump_yml
from xpdan.pipelines.pipeline_utils import (_timestampstr,
                                            clear_combine_latest, Filler,
                                            base_template)
from xpdtools.calib import _save_calib_param
from xpdtools.pipelines.raw_pipeline import *
from xpdview.callbacks import LiveWaterfall
from xpdconf.conf import glbl_dict

image_name = glbl_dict['image_field']
db = glbl_dict['exp_db']
mask_setting.update(setting='first')
calibration_md_folder = {'folder': 'xpdAcq_calib_info.yml'}

filler = Filler(db=db)
# Build the general pipeline from the raw_pipeline
raw_source = Stream(stream_name='raw source')

# TODO: change this when new dark logic comes
# Check that the data isn't a dark
dk_uid = (
    FromEventStream('start', (), upstream=raw_source)
    .map(lambda x: 'sc_dk_field_uid' in x)
)
# Fill the raw event stream
source = (
    raw_source
    .combine_latest(dk_uid)
    .filter(lambda x: x[1])
    .pluck(0)
    .starmap(filler)
)

# If new calibration uid invalidate our current calibration cache
(FromEventStream('start', ('detector_calibration_client_uid',), source)
    .unique(history=1)
    .map(lambda x: geometry_img_shape.lossless_buffer.clear()))

# Clear composition every start document
(FromEventStream('start', (), source)
    .sink(lambda x: clear_combine_latest(iq_comp, 1)))
FromEventStream('start', ('composition_string',), source).connect(composition)

# Calibration information
(FromEventStream('start', ('bt_wavelength',), source)
    .unique(history=1)
    .connect(wavelength))
(FromEventStream('start', ('calibrant',), source)
    .unique(history=1)
    .connect(calibrant))
(FromEventStream('start', ('detector',), source)
    .unique(history=1)
    .connect(detector))

(FromEventStream('start', (), source).
    map(lambda x: 'detector_calibration_server_uid' in x).
    connect(is_calibration_img))
# Only pass through new calibrations (prevents us from recalculating cals)
(FromEventStream('start', ('calibration_md',), source).
    unique(history=1).
    connect(geo_input))

start_timestamp = FromEventStream('start', ('time',), source)

start_docs = FromEventStream('start', (), source)
bg_query = (start_docs.map(query_background, db=db))
bg_docs = (bg_query
    .zip(start_docs)
    .starmap(temporal_prox)
    .filter(lambda x: x is not None)
    .map(lambda x: x[0].documents(fill=True))
    .flatten())

# Get bg dark
bg_dark_query = (FromEventStream('start', (), bg_docs)
    .map(query_dark, db=db)
    )
(FromEventStream('event', ('data', image_name),
                 bg_dark_query.map(lambda x: x[0].documents(fill=True))
                 .flatten())
 .connect(raw_background_dark))

# Get background
FromEventStream('event', ('data', image_name), bg_docs).connect(raw_background)

# Get foreground dark
fg_dark_query = (start_docs
    .map(query_dark, db=db))
(FromEventStream('event', ('data', image_name),
                 fg_dark_query
                 .map(lambda x: x[0].documents(fill=True)).flatten()
                 )
    .connect(raw_foreground_dark))

# Get foreground
FromEventStream('event', ('seq_num',), source, stream_name='seq_num'
                ).connect(img_counter)
FromEventStream('event', ('data', image_name), source, principle=True,
                stream_name='raw_foreground').connect(raw_foreground)

# Save out calibration data to special place
h_timestamp = start_timestamp.map(_timestampstr)
(gen_geo_cal
    .zip_latest(h_timestamp)
    .sink(lambda x: _save_calib_param(*x, calibration_md_folder['file_path'])))

# Write things to disk
# create filename string
descriptor_docs = FromEventStream('descriptor', (), source,
                                  event_stream_name='primary')
event_docs = FromEventStream('event', (), source, event_stream_name='primary')
all_docs = (
    event_docs
        .combine_latest(start_docs, descriptor_docs, emit_on=0)
        .starmap(lambda e, s, d: {'raw_event': e, 'raw_start': s,
                                  'raw_descriptor': d,
                                  'human_timestamp': _timestampstr(s['time'])})
)
start_yaml_string = (start_docs.map(lambda s: {'raw_start': s,
                                               'ext': '.yaml',
                                               # TODO: talk to BLS ask if
                                               #  they like this
                                               # 'analysis_stage': 'meta'
                                               })
    .map(lambda kwargs, string: render(string, **kwargs),
         string=base_template)
    )
start_yaml_string.map(clean_template).zip(start_docs).starsink(dump_yml)

filename_node = all_docs.map(lambda kwargs, string: render(string, **kwargs),
                             string=base_template)

# SAVING NAMES
filename_name_nodes = {}
for name, analysis_stage, ext in zip(
        ['dark_corrected_image_name', 'iq_name', 'tth_name', 'mask_fit2d_name',
         'mask_np_name', 'pdf_name', 'fq_name', 'sq_name'],
        ['dark_sub', 'iq', 'itth', 'mask', 'mask', 'pdf', 'fq', 'sq'],
        ['.tiff', '', '_tth', '', '_mask.npy', '.gr', '.fq', '.sq']
):
    if ext:
        temp_name_node =filename_node.map(render, analysis_stage=analysis_stage, ext=ext)
    else:
        temp_name_node = filename_node.map(render, analysis_stage=analysis_stage)

    filename_name_nodes[name] = temp_name_node.map(clean_template)
    (filename_name_nodes[name]
        .sink(lambda s: os.makedirs(os.path.split(s)[0], exist_ok=True)))
# '''
# SAVING
# TODO: NEED TO WRITE OUT YAML

# May rethink how we are doing the saving. If the saving was attached to the
# translation nodes then it would be run before the rest of the graph was
# processed.
# dark corrected img
(dark_corrected_foreground
    .zip(filename_name_nodes['dark_corrected_image_name'])
    .starsink(lambda img, s: imsave(s, img),
              stream_name='dark corrected foreground'))
# integrated intensities
(q.combine_latest(mean, emit_on=1).zip(filename_name_nodes['iq_name'])
    .map(lambda l: (*l[0], l[1]))
    .starsink(lambda x, y, n: save_output(x, y, n, 'Q'),
              stream_name='save integration {}'.format('Q')))
(tth.combine_latest(mean, emit_on=1).zip(filename_name_nodes['tth_name'])
    .map(lambda l: (*l[0], l[1]))
    .starsink(lambda x, y, n: save_output(x, y, n, '2theta'),
              stream_name='save integration {}'.format('tth')))
# Mask
(mask.zip_latest(filename_name_nodes['mask_fit2d_name'])
    .sink(lambda x: fit2d_save(np.flipud(x[0]), x[1])))
(mask.zip_latest(filename_name_nodes['mask_np_name'])
    .sink(lambda x: np.save(x[1], x[0])))
# PDF
(pdf.zip(filename_name_nodes['pdf_name']).map(lambda l: (*l[0], l[1]))
    .starsink(lambda r, gr, config, name: pdf_saver(r, gr, name, config),
              stream_name='pdf saver'))
# F(Q)
(fq.zip(filename_name_nodes['fq_name']).map(lambda l: (*l[0], l[1]))
    .starsink(lambda r, gr, config, name: pdf_saver(r, gr, name, config),
              stream_name='fq saver'))
# S(Q)
(sq.zip(filename_name_nodes['sq_name']).map(lambda l: (*l[0], l[1]))
    .starsink(lambda r, gr, config, name: pdf_saver(r, gr, name, config),
              stream_name='sq saver'))
# '''
# Visualization
# background corrected img
em_background_corrected_img = ToEventStream(bg_corrected_img,
                                            ('image',)).starsink(
    LiveImage('image', window_title='Background_corrected_img',
              cmap='viridis'))

# polarization corrected img with mask overlayed
ToEventStream(
    pol_corrected_img.combine_latest(mask).starmap(overlay_mask),
    ('image',)).starsink(LiveImage('image', window_title='final img',
                                   limit_func=lambda im: (
                                       np.nanpercentile(im, 2.5),
                                       np.nanpercentile(im, 97.5)
                                   ), cmap='viridis'))

# integrated intensities
(ToEventStream(mean.map(np.nan_to_num)
               .combine_latest(q, emit_on=0), ('iq', 'q'))
    .starsink(LiveWaterfall('q', 'iq', units=('1/A', 'Intensity'),
                            window_title='{} vs {}'.format('iq', 'q')),
              stream_name='{} {} vis'.format('q', 'iq')))

(ToEventStream(mean.map(np.nan_to_num)
               .combine_latest(tth, emit_on=0), ('iq', 'tth'))
    .starsink(LiveWaterfall('tth', 'iq', units=('Degree', 'Intensity'),
                            window_title='{} vs {}'.format('iq', 'tth')),
              stream_name='{} {} vis'.format('tth', 'iq')))
# F(Q)
ToEventStream(fq, ('q', 'fq')).starsink(
    LiveWaterfall('q', 'fq', units=('1/A', 'Intensity'),
                  window_title='F(Q)'), stream_name='F(Q) vis')

# PDF
ToEventStream(pdf, ('r', 'gr')).starsink(
    LiveWaterfall('r', 'gr', units=('A', '1/A**2'),
                  window_title='PDF'), stream_name='G(r) vis')

# Zscore
ToEventStream(z_score, ('z_score',)).starsink(
    LiveImage('z_score', cmap='viridis', window_title='z score',
              limit_func=lambda im: (-2, 2)), stream_name='z score vis')

# raw_source.visualize(os.path.expanduser('~/mystream.png'), source_node=True)
