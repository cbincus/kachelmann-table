from datetime import datetime, timedelta
import requests
from pathlib import Path
from io import BytesIO
from PIL import Image
import matplotlib.colors as mcolors
import pandas as pd
import numpy as np

# from colors.ColorLegend import kachelmann_precip_24h

# from colors.colors import kachelmann_precip_24h

class ColorLegend:
    def __init__(self, name, bounds, colors) -> None:
        if (len(colors) != len(bounds) + 1):
            raise ValueError('Bounds and colors do not match!')

        self.name = name
        self.bounds = bounds
        self.colors = colors

        self.length = len(colors)

        # cmap = mcolors.ListedColormap(colors[1:-1])
        # cmap.set_under(colors[0])
        # cmap.set_over(colors[-1])
        # self.cmap = cmap

        # self.norm = mcolors.BoundaryNorm(bounds, len(colors) - 2)

    def color_to_interval(self, index):
        if (index == 0):
            return (None, self.bounds[0])
        elif (index == self.length - 1):
            return (self.bounds[-1], None)
        else:
            return (self.bounds[index], self.bounds[index + 1])

kachelmann_precip_24h = ColorLegend(
    'Kachelmann Accumulated 24 h Precipitation',
    [
        0.1, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45,
        50, 60, 70, 80, 90, 100, 125, 150, 200, 300
    ],
    [
        (240, 240, 240),
        (180, 215, 255),
        (117, 186, 255),
        (53, 154, 255),
        (4, 130, 255),
        (0, 105, 210),
        (0, 54, 127),
        (20, 143, 27),
        (26, 207, 5),
        (99, 237, 7),
        (255, 244, 43),
        (232, 220, 0),
        (240, 96, 0),
        (255, 127, 39),
        (255, 166, 106),
        (248, 78, 120),
        (247, 30, 84),
        (191, 0, 0),
        (136, 0, 0),
        (100, 0, 127),
        (194, 0, 251),
        (221, 102, 255),
        (235, 166, 255),
        (249, 230, 255),
        (212, 212, 212),
        (150, 150, 150)
    ]
)

OUTFILE_PATH = Path('/home/cbincus')
OUTFILE_ARCHIVE_PATH = Path('/home/cbincus/archive')

IMG_URL_FORMAT = 'https://img1.kachelmannwetter.com/images/data/cache/model/download_model-de-999-1-xz_mod{{model}}_{{run}}_{{fcst_hour}}_{zoom_region}_{param_code}.png'

START_URL = 'https://kachelmannwetter.com/de/modellkarten/euro'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:98.0) Gecko/20100101 Firefox/98.0'
}

MODELS = {
    '4x4': 'swisseu',
    'EZ4': 'ezswiss',
    'HD': 'deuhd',
    'CH': 'swissmrf',
    'EU': 'ez',
    'GB': 'gbr',
    'DE': 'deu',
    'US': 'usa',
    'CA': 'can',
    'AU': 'aus'
}

MODELS_00_12UTC = ['EU', 'CA']

DELTA = 1.

zoom_region = 21747
zoom_resolution = 0.4 # km
crop_xstart = 160
crop_ystart = 200
crop_x = 200
crop_y = 200

param_code = 63
param_name = '24-hr Accumulated Total Precipitation [mm]'

img_url_zoom_param = IMG_URL_FORMAT.format(zoom_region=zoom_region, param_code=param_code)

date_now = datetime.now().date()
# date_now = datetime(2022, 8, 9, 3, 0)
datetime_now_00utc = datetime(date_now.year, date_now.month, date_now.day)

datetime_next_00utc = datetime_now_00utc + timedelta(days=1)
datetime_prev_00utc = datetime_now_00utc - timedelta(days=1)

run_date = datetime_prev_00utc.date()

df = pd.DataFrame(
    columns=MODELS.keys(),
    index=[0, 6, 12, 18]
)
df.index.name = 'Run Hour'

# Convert index to dataframe
old_idx = df.index.to_frame()

# Insert new level at specified location
old_idx.insert(0, 'Run Date', run_date)

# Convert back to MultiIndex
df.index = pd.MultiIndex.from_frame(old_idx)

df_helper = df.copy()

with requests.Session() as s:
    s.get(START_URL, headers=HEADERS)

    for model in MODELS.keys():
        run_hours = [0, 12] if model in MODELS_00_12UTC else [0, 6, 12, 18]

        for run_hour in run_hours:
            run_datetime = datetime_prev_00utc + timedelta(hours=run_hour)

            fcst_timedelta = datetime_next_00utc - run_datetime
            fcst_hour = int(fcst_timedelta.total_seconds()) // 3600

            img_url = img_url_zoom_param.format(
                model=MODELS[model], 
                run=f'{datetime_prev_00utc.strftime("%Y%m%d")}{run_hour:02d}', 
                fcst_hour=fcst_hour
            )

            r = s.get(img_url, headers=HEADERS)
            r.close()

            if (r.status_code == 200):
                img = Image.open(BytesIO(r.content))
                crop = img.crop(
                    (crop_xstart, crop_ystart, 
                    crop_xstart + crop_x, crop_ystart + crop_y)
                )

                crop_colors = crop.convert('RGB').getcolors()
                crop_colors_rgb = [cc[1] for cc in crop_colors]

                ccrgb_indices = []

                for ccrgb in crop_colors_rgb:
                    try:
                        ccrgb_index = kachelmann_precip_24h.colors.index(ccrgb)
                        ccrgb_indices.append(ccrgb_index)
                    except ValueError:
                        pass

                max_color_index = max(ccrgb_indices)
                interval = kachelmann_precip_24h.color_to_interval(max_color_index)

                if interval[0] == None:
                    helper_value = interval[1] - DELTA
                    value = f'<{interval[1]}'
                elif interval[1] == None:
                    value = f'>{interval[0]}'
                    helper_value = interval[0] + DELTA
                else:
                    value = f'{interval[0]}..{interval[1]}'
                    helper_value = (interval[0] + interval[1]) / 2
                    
                df.loc[(run_date, run_hour), model] = value
                df_helper.loc[(run_date, run_hour), model] = helper_value

df.replace(np.nan, '---', inplace=True)

cmap = mcolors.ListedColormap(np.array(kachelmann_precip_24h.colors) / 255)
norm = mcolors.BoundaryNorm(kachelmann_precip_24h.bounds, cmap.N)

def highlight(x):
    return df_helper.applymap(norm).applymap(cmap).applymap(mcolors.rgb2hex).applymap(lambda x: f'background-color: {x};')

df_styled = df.style.apply(highlight, axis=None)

caption = (f'{param_name}<br>')
df_styled.set_caption(caption)

df_styled_html = df_styled.to_html()

html_title = f'Kachelmann Summary {date_now.strftime("%d.%m.%Y")}'

location = 'Chisinau'
region_xdim = crop_x * zoom_resolution
region_ydim = crop_y * zoom_resolution

h1 = f'Maximum Values in {region_xdim:g}x{region_ydim:g} km {location}-centered square'
h2 = f'Valid: {date_now.strftime("%d %h %Y (UTC)")}'

html = (
    '''<html>
        <head>
            <title>{0}</title>
        </head>
        <body>
            <h1>{1}</h1>
            <h2>{2}</h2>
            {3}
        </body>
    </html>'''.format(html_title, h1, h2, df_styled_html)
)

with open(OUTFILE_PATH / 'kachelmann.html', 'w') as f:
    f.write(html)

date_for_archive = f'{date_now.strftime("%Y%m%d")}'
with open(OUTFILE_ARCHIVE_PATH / f'kachelmann_{date_for_archive}.html', 'w') as f_archive:
    f_archive.write(html)