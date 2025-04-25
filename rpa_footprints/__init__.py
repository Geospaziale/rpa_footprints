# Ensure all packages in the requirements are installed, and install with pip if not
try:
    import csv
    import geopandas as gpd
    import geojson
    import math
    import os
    import re
    import utm
    from datetime import datetime
    from shapely.geometry import Polygon, mapping
except:
    print('Installing plugin requirements for the first time.')
    import os
    try:
        import pip
    except:
        raise ValueError('pip is not installed. Ensure this is installed for QGIS before you run this plugin.')
    current_path = __file__
    requirements_path = os.path.join(os.path.dirname(os.path.dirname(current_path)), 'requirements.txt')
    pip.main(['install', '-r', requirements_path])