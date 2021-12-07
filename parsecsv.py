import yaml
import re
import requests
from requests.exceptions import HTTPError
import csv
import math
import glob
from lxml import etree
from number_parser import parse_number
from pykml.helpers import set_max_decimal_places
from pykml.factory import KML_ElementMaker as KML

# Requires pyKML, lxml, number_parser, pyyaml
# Download with 'pip install pykml lxml number_parser'
# Also requires google map key. Get one at the google developer console


try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

# Load the configuraiton file
config = dict()
with open('./config.yml') as file:
    yml = yaml.load(file.read(), Loader=Loader)

    # Parse recursively to alter all dictionary keys
    def parse_ymlconfiguration(cfg: dict):
        result = dict()
        if isinstance(cfg, dict):
            for k, v in dict(cfg).items():
                if isinstance(v, dict) or isinstance(v, list):
                    v = parse_ymlconfiguration(v)
                result[str(k).lower().replace(' ', '_')] = v
        elif isinstance(cfg, list):
            result = list()
            for x in cfg:
                if isinstance(x, dict) or isinstance(x, list):
                    x = parse_ymlconfiguration(x)
                result.append(x)
        else:
            return cfg
        return result

    config = parse_ymlconfiguration(yml)
    if 'googlemaps_key' in config:
        GOOGLEMAPS_KEY = config['googlemaps_key']
    else:
        print('No google maps key found in config file.')
        print('There will be no conversion to coordinates.')
    assert 'description' in config, 'No description found in config file.'
    assert 'display' in config, 'No display found in config file.'
    assert 'categories' in config, 'No categories found in config file.'


# Load from json
with open('settings.json', 'r') as file:
    import json
    allinfo = json.load(file)
    POSSIBLE_KEYS = allinfo['description']
    DISPLAY_AND_UNITS = allinfo['display']
    STYLE_INFO = allinfo['categories']
    GOOGLEMAPS_KEY = allinfo['mapskey']


def tofloat(num: str) -> float:
    """Converts a string to a float, if possible."""
    num = re.sub(r'[<>,]', '', num)
    try:
        return parse_number(num) or float(num)
    except ValueError:
        return None


def normalize_place(place: dict) -> dict:
    """
    Converts a place to a dictionary with all keys required by the config file.

    Args:
        place (dict): The raw csv row

    Returns:
        dict: a place containing all required keys
    """
    possible_keys = POSSIBLE_KEYS.copy()

    # Create blank normalized place
    normalized_place = {k: str() for k in POSSIBLE_KEYS}

    # Fill in normalized place
    for col_name, col_value in place.items():
        # Scan each option for a match
        for key_name, syn_lst in possible_keys.items():
            # Check each key, including the name
            for key_to_check in list(syn_lst) + [key_name, ]:
                # If we find a match in the column name, we are DONE with that key but NOT with the column
                if key_to_check.lower() in col_name.lower():
                    # Key found. Attempt to parse if it is a number
                    if as_number := tofloat(col_value):
                        normalized_place[key_name] = as_number
                    else:
                        normalized_place[key_name] = str(col_value).title()
                    #del possible_keys[key_name]
                    break
            # else:
            #    continue
            # break
    print('\n\n')
    print(place)
    print(normalized_place)
    return normalized_place


def address_to_coords(address: str) -> tuple:
    """
    Converts an address to coordinates.
    Requires a google maps key to be set in the config file.

    Args:
        address (str): The street address or intersection

    Returns:
        tuple: latitude, longitude
    """
    # Use google maps api to get coordinates
    resp = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params={
        'address': address.encode('ascii', 'xmlcharrefreplace'),
        'sensor': 'false',
        'key': GOOGLEMAPS_KEY
    })
    try:
        resp.raise_for_status()
        resp = resp.json()
        return (
            resp['results'][0]['geometry']['location']['lat'],
            resp['results'][0]['geometry']['location']['lng']
        )
    except (IndexError, HTTPError) as e:
        # log error
        print(
            f'Error getting coords for {address}.\nError: {e}'
        )
        return tuple()


def add_coords_to_place(place: dict) -> dict:
    """
    Updates fields in a place to include coordinates,
    calling address_to_coords() if necessary.

    Args:
        place (dict): The place to update

    Returns:
        dict: The place with coordinates
    """

    if 'location' in place and len(place['location']) > 3:
        # if there are any non numbers in the location
        if any(not c in '0123456789' for c in re.sub(r'N|E|S|W|-|,|\s+|\.|\,', '', place['location'])):
            print(f'{place["location"]} is an address. Converting to coords')
            place['address'] = place['location']
            place['location'] = address_to_coords(place['location'])
            print(f'Coords: {place["location"]}')
        else:
            print(f'{place["location"]} is already coords. Casting...')
            place['location'] = tuple(
                map(lambda x: float(x.strip()), place['location'].split(',')))
            print(f'Coords: {place["location"]}')
    return place


def calculate_style(place: dict) -> KML.Style:
    """
    Categorizes a place and sets its style according
    to the config file.

    Args:
        place (dict): The place to categorize

    Returns:
        KML.Style: The style to use for the place
    """
    style_info = STYLE_INFO['*']
    print(f'Calculating style for {place["name"]}')
    for style_key, style_val in STYLE_INFO.items():
        if style_key == '*':
            continue

        # If it's a combined style
        if '&' in style_key:
            # Generate combined identifiers
            all_identifiers = [STYLE_INFO[style]['identifiers']
                               for style in style_key.split('&') if style in STYLE_INFO]
            # TODO: finish. It must match all identifiers, which each match any part of the place type
            if all(any(identifier in place['type'].lower() for identifier in sub_identifiers) for sub_identifiers in all_identifiers):
                style_info = {**style_info, **style_val}
                place['category'] = style_key
                print(f'{place["type"]} matches {style_key}')

        # If it's a single style
        # Check if any identifier matches
        elif any(identifier in place['type'].lower() for identifier in style_val['identifiers']):
            style_info = {**style_info, **style_val}
            place['category'] = style_key
            print(f'{place["type"]} matches {style_key}')

    # Set the place's style
    if 'category' not in place:
        place['category'] = 'unknown'

    # Now, let's try to find a size based on this things size
    if 'size' in place and (capacity := parse_number(str(place['size']))):
        capacity = sorted((1, capacity, 1000))[1]
        style_info['scale'] *= math.pow(capacity / 20, 0.25)
        style_info['label_scale'] *= math.pow(capacity / 20, 0.25)

    print(style_info['scale'])

    # Now that we gathered the info, create the style
    # Yes, this is extremely verbose and not correct but it's a quick and dirty solution
    # Ideally, we'd use style links and overrides to make the resulting kml more readable
    return KML.Style(
        KML.IconStyle(
            KML.scale(style_info['scale']),
            KML.color(style_info['color']),
            KML.Icon(
                KML.href(style_info['icon'])
            )
        ),
        KML.LabelStyle(
            KML.scale(style_info['label_scale'])
        ),
        KML.LineStyle(
            KML.color(style_info['color'])
        ),
        KML.PolyStyle(
            KML.color(style_info['color'])
        )
    )


def place_to_kml(place: dict) -> KML.Placemark:
    """
    Converts a place to a KML placemark,
    calling calculate_style() to set the style.

    Args:
        place (dict): The place with coordinates marked

    Returns:
        KML.Placemark: The placemark ready to add to the kml
    """

    description = str()
    for key, unit in DISPLAY_AND_UNITS.items():
        if key in place and place[key]:
            description += f'<p>{key.title()}: {place[key]} {unit}</p>'

    # Create KML Placemark
    return KML.Placemark(
        KML.name(place['name']),
        KML.description(
            f'<h1><b>{place["name"]}</b></h1>'
            + description
        ),
        KML.Point(
            KML.coordinates(
                ','.join(map(str, reversed(place['location'])))
            )
        ),
        calculate_style(place)
    )


def main(docname: str, data_sources: list or str):
    if(isinstance(data_sources, str)):
        data_sources = [data_sources]

    data_files = list()
    for data_source in data_sources:
        if os.path.isfile(data_source) and data_source.endswith('.csv'):
            data_files.append(data_source)
        elif os.path.isdir(data_source):
            data_files.extend(glob.glob(os.path.join(data_source, '*.csv')))
        elif data_source.strip() == '*':
            data_files.extend(glob.glob('*.csv'))
        else:
            print(f'{data_source} is not a valid data source')

    # Load all data file contents as raw data
    raw_places = list()
    for path in data_files:
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for line in reader:
                raw_places.append(line)

    print(raw_places)
    normalized_places = list(map(normalize_place, raw_places))
    print('Places:\n\n', normalized_places)
    normalized_places = list(map(add_coords_to_place, normalized_places))
    normalized_places = list(filter(lambda p: len(
        str(p['location'])) > 3, normalized_places)
    )
    print('Normalized:\n\n', normalized_places)
    kml_places = list(map(place_to_kml, normalized_places))

    kml_document = KML.kml(
        KML.Document(
            KML.name(docname.title()),
            *kml_places
        )
    )

    with open(f'{docname.lower()}.kml', 'w') as f:
        f.write(etree.tostring(kml_document, pretty_print=True).decode('utf-8'))

    set_max_decimal_places(kml_document, max_decimals={
        'latitude': 6,
        'longitude': 6
    })

    with open(f'{docname.lower()}.kml', 'w') as f:
        f.write(etree.tostring(kml_document, pretty_print=True).decode('utf-8'))


if __name__ == '__main__':
    def dontprint(*args, **kwargs):
        pass
    print = dontprint
    main()
