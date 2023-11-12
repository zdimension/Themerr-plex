# -*- coding: utf-8 -*-

# standard imports
import time

# plex debugging
try:
    import plexhints  # noqa: F401
except ImportError:
    pass
else:  # the code is running outside of Plex
    from plexhints.log_kit import Log  # log kit
    from plexhints.parse_kit import JSON  # parse kit

# imports from Libraries\Shared
import requests
from typing import Union

database_cache = {}
cache_updating = False
last_cache_update = 0

db_field_name = dict(
    games={'igdb': 'id'},
    game_collections={'igdb': 'id'},
    game_franchises={'igdb': 'id'},
    movies={'themoviedb': 'id', 'imdb': 'imdb_id'},
    movie_collections={'themoviedb': 'id'},
)


def update_cache():
    # type: () -> None
    """
    Update the ThemerrDB cache.

    The pages.json file is fetched for all database types, then each all_page_N.json file is fetched to form the
    complete set of available IDs.

    Attempting to update the cache while an update is already in progress will wait until the current update is
    complete.

    Updating the cache less than an hour after the last update is a no-op.
    """
    Log.Info('Updating ThemerrDB cache')

    global database_cache, cache_updating, last_cache_update

    if time.time() - last_cache_update < 3600:
        Log.Info('Cache updated less than an hour ago, skipping')
        return

    if cache_updating:
        while cache_updating:
            Log.Info('Cache updating...')
            time.sleep(1)

    cache_updating = True

    try:
        for database_type, databases in db_field_name.items():
            try:
                pages = JSON.ObjectFromURL(
                    cacheTime=3600,
                    url='https://app.lizardbyte.dev/ThemerrDB/{}/pages.json'.format(database_type),
                    errors='ignore'  # don't crash the plugin
                )
                page_count = pages['pages']

                id_index = {db: set() for db in databases}

                for page in range(page_count):
                    page_data = JSON.ObjectFromURL(
                        cacheTime=3600,
                        url='https://app.lizardbyte.dev/ThemerrDB/{}/all_page_{}.json'.format(database_type, page + 1),
                        errors='ignore'  # don't crash the plugin
                    )

                    for db in databases:
                        id_index[db].update(str(item[db_field_name[database_type][db]]) for item in page_data)

                database_cache[database_type] = id_index

                Log.Info('{}: database updated'.format(database_type))
            except Exception as e:
                Log.Error('{}: Error retrieving page index from ThemerrDB: {}'.format(database_type, e))

                database_cache[database_type] = {}

        last_cache_update = time.time()
    finally:
        cache_updating = False


def item_exists(database_type, database, id):
    # type: (str, str, Union[int, str]) -> bool
    """
    Check if an item exists in the ThemerrDB.

    Parameters
    ----------
    database_type : str
        The type of database to check for the item.

    database : str
        The database to check for the item.

    id : Union[int, str]
        The ID of the item to check for.

    Returns
    -------
    bool
        True if the item exists in the ThemerrDB, otherwise False.

    Examples
    --------
    >>> item_exists(database_type='games', database='igdb', id=1234)
    True

    >>> item_exists(database_type='movies', database='themoviedb', id=1234)
    False
    """
    if database_type not in db_field_name:
        Log.Critical('"{}" is not a valid database_type. Allowed values are: {}'
                     .format(database_type, db_field_name.keys()))
        return False

    if database_type not in database_cache:
        update_cache()

    type_cache = database_cache[database_type]
    return database in type_cache and str(id) in type_cache[database]


def get_pending_themes():
    # type: () -> set[str]
    """
    Get the URLs of all pending theme requests.
    
    Returns
    -------
    set[str]
        A set of URLs of all pending theme requests.
        
    Examples
    --------
    >>> next(get_pending_themes())
    'https://www.themoviedb.org/movie/1234-thing'
    """

    url = "https://api.github.com/repos/LizardByte/ThemerrDB/issues?state=open&labels=request-theme&per_page=100"
    results = set()

    Log.Info('Pending list updating...')

    while True:
        r = requests.get(url)
        content = r.json()

        for obj in content:
            try:
                issue_body = obj['body'] 
                # body is in the form
                # "### Database URL\n\nhttps://www.themoviedb.org/movie/1234-thing\n\n" +
                # "### YouTube Theme Song Video URL\n\nhttps://www.youtube.com/watch?v=fakevideo"
                item_url = issue_body.split('### Database URL\n\n')[1].split('\n\n')[0]  # yeah...
                assert item_url.startswith('http')
                results.add(item_url)
            except:
                continue

        if 'next' in r.links:
            url = r.links['next']['url']
        else:
            break

    Log.Info('Pending list updated ({} items)'.format(len(results)))
    Log.Debug('Pending list: {}'.format(results))

    return results
