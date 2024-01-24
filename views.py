from flask import Blueprint, render_template, request, flash, session, url_for, redirect
import sqlite3
from io import BytesIO
from matplotlib.figure import Figure
from matplotlib.patches import Circle
import base64

views = Blueprint('views', __name__)

DATABASE = 'Music.db'

'''
    Create pie chart

    args: 
        stats(list) a list of tuples containing artist data

    returns: 
        str: url for pie chart image
'''


def make_pie(stats):
    data = {}

    # Add data to dict
    for row in stats:
        if row[4] not in data:
            data[row[4]] = 1
        else:
            data[row[4]] += 1

    # Convert small percentage categories to category 'other'
    other_genres = []
    other_ct = 0
    for key, value in data.items():
        if value/len(stats) < 0.02:
            other_genres.append(key)
            other_ct += value

    for key in other_genres:
        data.pop(key)

    if other_genres:
        label = "Other: " + ', '.join(other_genres)
    else:
        label = "Other"

    data[label] = other_ct
    data = {k: v for k, v in sorted(data.items(), key=lambda item: item[1])}

    labels = data.keys()
    sizes = [x/len(stats) for x in data.values()]

    fig = Figure()

    ax = fig.add_subplot(1, 1, 1)

    # Create the pie chart
    wedges, text, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    centre_circle = Circle((0, 0), 0.70, fc='white')
    ax.add_artist(centre_circle)
    ax.axis('equal')

    # Save the pie chart image to buffer
    buf = BytesIO()
    fig.savefig(buf, format='png')
    data = base64.b64encode(buf.getbuffer()).decode('ascii')
    url = f'data:image/png;base64,{data}'

    return url


'''
    Create bar chart

    args: 
        stats (list): a list of tuples containing song data

    returns: 
        str: url for bar chart image
'''


def make_chart(stats):
    # Create dict to store data
    categories = {
        'popularity': [],
        'danceability': [],
        'energy': [],
        'loudness': [],
        'speechiness': [],
        'acousticness': [],
        'instrumentalness': [],
        'liveness': [],
        'valence': []
    }

    # Add data to dict
    for row in stats:
        categories['popularity'].append(row[9])
        categories['danceability'].append(row[10])
        categories['energy'].append(row[11])
        categories['loudness'].append(row[12])
        categories['speechiness'].append(row[13])
        categories['acousticness'].append(row[14])
        categories['instrumentalness'].append(row[15])
        categories['liveness'].append(row[16])
        categories['valence'].append(row[17])

    values = [(sum(x)/len(x)) for x in categories.values()]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
              '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22']

    fig = Figure()
    ax = fig.add_axes([0.1, 0.25, 0.8, 0.6])

    # Create the bar chart
    ax.bar(categories.keys(), values, color=colors, width=0.4)

    ax.set_xlabel('Statistic')
    ax.set_ylabel('Rating')
    ax.set_title('Statistics for your search!')
    ax.set_xticklabels(categories.keys(), rotation=90)

    # Save the bar chart image to buffer
    buf = BytesIO()
    fig.savefig(buf, format='png')
    data = base64.b64encode(buf.getbuffer()).decode('ascii')
    url = f'data:image/png;base64,{data}'

    return url


'''
    Get song data based on user queries

    args: 
        song (str): user search query for song,
        artist (str): user search query for artist,
        date1 (int): user search query for starting year,
        date2 (int): user search query for ending year,
        explicit (bool): user selection of explicit or not,
        stat (str): stat to calculate for advanced statistics,
        category (str): category for advanced statistics,
        chart (bool): user selection to show chart or not
    
    returns: 
        results (list): list of tuples containing song data,
        page_results (list): list of tuples containing song data to display on current page,
        stat_result (float): result of advanced statistics calculation,
        page (int): current page to display,
        song_chart_url (str): link to song chart image
'''


def get_song_data(song, artist, order, date1, date2, explicit, stat, category, chart):

    # Establish connection to db
    conn = sqlite3.connect('Music.db')
    cur = conn.cursor()

    query1 = ""

    # Create base query for advanced statistics
    if stat and category:
        g = ""
        if stat == 'STDDEV':
            query1 = f"""SELECT SQRT( SUM(({category} - mean_value) * ({
                category} - mean_value)) / COUNT(*) ) AS standard_deviation FROM Song,(SELECT AVG({category}) AS mean_value FROM Song) WHERE """
        elif stat == 'median':
            query1 = f"""WITH OrderedData AS (SELECT {category}, ROW_NUMBER() OVER (ORDER BY {
                category}) AS RowAsc, ROW_NUMBER() OVER (ORDER BY {category} DESC) AS RowDesc FROM Song WHERE """
        elif stat == 'MIN' or stat == 'MAX':
            g = " *,"
            query1 = f"""SELECT{g} {
                stat}({category}) AS col FROM Song WHERE """
        else:
            query1 = f"""SELECT {stat}
                ({category}) AS col FROM Song WHERE """

    # Create base query for results
    query = "SELECT * FROM Song WHERE "
    conditions = []

    # Add Conditions based on user input
    if song:
        conditions.append(f'''Song LIKE "%{song}%"''')
    if artist:
        conditions.append(f'''Artist LIKE "%{artist}%"''')
    if date1:
        conditions.append(f'''ReleaseDate > {date1}''')
    if date2:
        conditions.append(f'''ReleaseDate < {date2}''')
    if not explicit:
        conditions.append(f'''Explicit = "false"''')

    # Join conditions
    if conditions:
        query += " AND ".join(conditions)
        if query1:
            query1 += " AND ".join(conditions)
    else:
        query += "1"
        if query1:
            query1 += "1"

    # Specify order based on user input
    if order:
        query += f''' ORDER BY "{order}" DESC'''

    # Execute queries and receive results
    try:
        cur.execute(query)
        results = cur.fetchall()
    except Exception:
        flash("Error: Something went wrong.", category="error")
        return "", "", "", ""

    # Determine current page to display
    if len(results) > 30:
        page = request.args.get('page', default=1, type=int)
        session['song_page'] = page
        per_page = 30
        offset = (page - 1) * per_page
        query2 = query + f" LIMIT {per_page} OFFSET {offset}"
    else:
        page = 1
        session['song_page'] = 1
        query2 = ""

    if category and stat == 'median':
        query1 += f""") SELECT AVG({
            category}) AS median FROM OrderedData WHERE RowAsc IN (RowDesc, RowDesc + 1, RowDesc - 1)"""

    stat_result = ""
    page_results = ""
    if query1:
        try:
            cur.execute(query1)
            stat_result = cur.fetchone()
        except Exception:
            flash("Error: Something went wrong.", category="error")
            return "", "", "", ""

    if query2:
        try:
            cur.execute(query2)
            page_results = cur.fetchall()
        except Exception:
            flash("Error: Something went wrong.", category="error")
            return "", "", "", ""

    # Close connection
    cur.close()
    conn.close()

    if chart:
        song_chart_url = make_chart(results)
    else:
        song_chart_url = ''

    return results, page_results, stat_result, page, song_chart_url


'''
    Get album data based on user queries

    args: 
        title (str): user search query for album title,
        order (str): order for results,
        date1 (int): user search query for starting year,
        date2 (int): user search query for ending year,
        stat (str): stat to calculate for advanced statistics,
        category (str): category for advanced statistics
    
    returns: 
        results (list): list of tuples containing album data,
        page_results (list): list of tuples containing album data to display on current page,
        stat_result (float): result of advanced statistics calculation,
        page (int): current page to display
'''


def get_album_data(title, order, date1, date2, stat, category):

    # Establish connection to db
    conn = sqlite3.connect('Music.db')
    cur = conn.cursor()

    query1 = ""
    # Create base query for advanced statistics based on user input
    if stat and category:
        g = ""
        if stat == 'STDDEV':
            query1 = f"""SELECT SQRT( SUM(({category} - mean_value) *
                    ({category} - mean_value)) / COUNT(*) ) AS
                    standard_deviation FROM Album,(SELECT AVG({
                category}) AS mean_value FROM Album) WHERE """
        elif stat == 'median':
            query1 = f"""WITH OrderedData AS (SELECT {category}, ROW_NUMBER() OVER (ORDER BY {
                category}) AS RowAsc, ROW_NUMBER() OVER (ORDER BY {category} DESC) AS
                RowDesc FROM Album WHERE """
        elif stat == 'MIN' or stat == 'MAX':
            g = " *,"
            query1 = f"""SELECT{g} {
                stat}({category}) AS col FROM Album WHERE """
        else:
            query1 = f"SELECT {stat}({category}) AS col FROM Album WHERE "

    # Create base query for results
    query = '''SELECT DISTINCT Album.*, Song.AlbumImageURL 
            FROM Album LEFT JOIN Song ON 
            Album.Album = Song.Album WHERE '''
    conditions = []

    # Add Conditions based on user input
    if title:
        conditions.append(f'''Album.Album LIKE "%{title}%"''')
    if date1:
        conditions.append(f'''Album.ReleaseDate > {date1}''')
    if date2:
        conditions.append(f'''Album.ReleaseDate < {date2}''')

    # Join conditions
    if conditions:
        query += " AND ".join(conditions)
        if query1:
            query1 += " AND ".join(conditions)
    else:
        query += "1"
        if query1:
            query1 += "1"
    if category and stat == 'median':
        query1 += f""") SELECT AVG({
            category}) AS median FROM OrderedData WHERE RowAsc IN (RowDesc, RowDesc + 1, RowDesc - 1)"""

    # Order results based on user input
    if order:
        query += f''' ORDER BY "Album.{order}" DESC'''

    # Execute queries and receive results
    try:
        cur.execute(query)
        results = cur.fetchall()
    except Exception as e:
        flash("Error: Something went wrong.", category="error")
        return "", "", "", ""

    # Determine results for current page
    if len(results) > 30:
        page = request.args.get('page', default=1, type=int)
        session['album_page'] = page
        per_page = 30
        offset = (page - 1) * per_page
        query2 = query + f" LIMIT {per_page} OFFSET {offset}"
    else:
        page = 1
        session['album_page'] = 1
        query2 = ""

    stat_result = ""
    page_results = ""
    if query1:
        try:
            cur.execute(query1)
            stat_result = cur.fetchone()
        except Exception:
            flash("Error: Something went wrong", category="error")
            return "", "", "", ""
    if query2:
        try:
            cur.execute(query2)
            page_results = cur.fetchall()
        except Exception:
            flash("Error: Something went wrong", category="error")
            return "", "", "", ""

    # Close connection to db
    cur.close()
    conn.close()

    return results, page_results, stat_result, page


'''
    Get artist data based on user queries

    args: 
        search (str): user search query for artist name,
        order (str): order to display results,
        genre (str): user search query for genre,
        pie (bool): user selection whether to generate pie chart or not
    
    returns: 
        results (list): list of tuples containing song data,
        page_results (list): list of tuples containing song data to display on current page,
        page (int): current page to display,
        pie_url (str): link to pie chart image
'''


def get_artist_data(search, order, genre, pie):

    # Establish connection to db
    conn = sqlite3.connect('Music.db')
    cur = conn.cursor()

    # Base Query
    query = '''SELECT Artist.*, COUNT(Song.Song) AS 
        num_tracks FROM Artist LEFT JOIN Song ON 
        Artist.Artist=Song.Artist WHERE '''
    conditions = []

    # Add Conditions based on user input
    if search:
        conditions.append(f'''Artist.Artist LIKE "%{search}%"''')
    if genre:
        conditions.append(f'''Artist.genre LIKE "%{genre}%"''')

    # Join conditions
    if conditions:
        query += " AND ".join(conditions)
    else:
        query += "1"

    query += " GROUP BY Artist.Artist"

    # Order results based on user input
    if order:
        query += f''' ORDER BY "{order}" DESC'''

    # Execute queries and receive results
    try:
        cur.execute(query)
        results = cur.fetchall()
    except Exception:
        flash("Error: Something went wrong.", category="error")
        return "", "", "", ""

    # Determine results to show on current page
    if len(results) > 30:
        page = request.args.get('page', default=1, type=int)
        session['artist_page'] = page
        per_page = 30
        offset = (page - 1) * per_page
        query2 = query + f" LIMIT {per_page} OFFSET {offset}"
    else:
        page = 1
        session['artist_page'] = 1
        query2 = ""

    page_results = ""
    if query2:
        try:
            cur.execute(query2)
            page_results = cur.fetchall()
        except Exception:
            flash("Error: Something went wrong.", category="error")
            return "", "", "", ""

    # Close connection to db
    cur.close()
    conn.close()

    if pie:
        pie_url = make_pie(results)
    else:
        pie_url = ''

    return results, page_results, page, pie_url


@views.route('/')
def home():
    return render_template('home.html')


@views.route('/songs', methods=['GET', 'POST'])
def songs():
    if request.method == 'POST':

        session.clear()
        search = request.form.get('song')
        artist = request.form.get('artist')
        order = request.form.get('order')
        date1 = request.form.get('date1')
        date2 = request.form.get('date2')
        explicit = request.form.get('explicit')
        stat = request.form.get('stat')
        category = request.form.get('category')
        chart = request.form.get('chart')

        session['song_search_data'] = {
            'song': search,
            'artist': artist,
            'order': order,
            'date1': date1,
            'date2': date2,
            'explicit': explicit,
            'stat': stat,
            'category': category,
            'chart': chart
        }

        results, page_results, stat_result, page, song_chart_url = get_song_data(
            search, artist, order, date1, date2, explicit, stat, category, chart)

        count = len(results)
        flash(f'''Retrieved {
              count} result(s) matching your search.''', category="success")

        return render_template('songs.html', results=results, search=search, chart=chart,
                               artist=artist, order=order, date1=date1, date2=date2, explicit=explicit,
                               stat=stat, category=category, page_results=page_results,
                               stat_result=stat_result, page=page, song_chart_url=song_chart_url)
    else:
        search_data = session.get('song_search_data')
        if search_data:
            song = session['song_search_data']['song']
            artist = session['song_search_data']['artist']
            order = session['song_search_data']['order']
            date1 = session['song_search_data']['date1']
            date2 = session['song_search_data']['date2']
            explicit = session['song_search_data']['explicit']
            stat = session['song_search_data']['stat']
            category = session['song_search_data']['category']
            chart = session['song_search_data']['chart']

            results, page_results, stat_result, page, song_chart_url, = get_song_data(
                song, artist, order, date1, date2, explicit, stat, category, chart)

            return render_template('songs.html', results=results, search=song, chart=chart,
                                   artist=artist, order=order, date1=date1, date2=date2, explicit=explicit,
                                   stat=stat, category=category, page_results=page_results,
                                   stat_result=stat_result, page=page, song_chart_url=song_chart_url)

        return render_template('songs.html')


@views.route('/albums', methods=['GET', 'POST'])
def albums():
    if request.method == 'POST':
        search = request.form.get('album')
        order = request.form.get('order')
        date1 = request.form.get('date1')
        date2 = request.form.get('date2')

        stat = request.form.get('stat')
        category = request.form.get('category')

        session['album_search_data'] = {
            'title': search,
            'order': order,
            'date1': date1,
            'date2': date2,
            'stat': stat,
            'category': category
        }

        results, page_results, stat_result, page = get_album_data(
            search, order, date1, date2, stat, category)

        count = len(results)
        flash(f'''Retrieved {
              count} result(s) matching your search.''', category="success")

        return render_template('albums.html', results=results, search=search, order=order,
                               date1=date1, date2=date2, page_results=page_results,
                               stat_result=stat_result, stat=stat, category=category, page=page)
    else:
        search_data = session.get('album_search_data')
        if search_data:
            title = session['album_search_data']['title']
            order = session['album_search_data']['order']
            date1 = session['album_search_data']['date1']
            date2 = session['album_search_data']['date2']
            stat = session['album_search_data']['stat']
            category = session['album_search_data']['category']

            results, page_results, stat_result, page = get_album_data(
                title, order, date1, date2, stat, category)

            return render_template('albums.html', results=results, search=title, order=order,
                                   date1=date1, date2=date2, page_results=page_results,
                                   stat_result=stat_result, stat=stat, category=category, page=page)

        return render_template('albums.html')


@views.route('/artists', methods=['GET', 'POST'])
def artists():
    if request.method == 'POST':
        search = request.form.get('artist')
        order = request.form.get('order')
        genre = request.form.get('genre')
        pie = request.form.get('pie')

        session['artist_search_data'] = {
            'name': search,
            'order': order,
            'genre': genre,
            'pie': pie
        }

        results, page_results, page, pie_url = get_artist_data(
            search, order, genre, pie)

        count = len(results)
        flash(f'''Retrieved {
              count} result(s) matching your search.''', category="success")

        return render_template('artists.html', results=results, search=search, order=order, pie=pie,
                               genre=genre, page_results=page_results, page=page, pie_url=pie_url)
    else:
        search_data = session.get('artist_search_data')
        if search_data:
            name = session['artist_search_data']['name']
            order = session['artist_search_data']['order']
            genre = session['artist_search_data']['genre']
            pie = session['artist_search_data']['pie']

            results, page_results, page, pie_url = get_artist_data(
                name, order, genre, pie)

            return render_template('artists.html', results=results, search=name, order=order, pie=pie,
                                   genre=genre, page_results=page_results, page=page, pie_url=pie_url)

    return render_template('artists.html')


@views.route('/change', methods=['GET', 'POST'])
def change():
    if request.method == 'POST':
        song_name = request.form.get('trackName')
        song_artist = request.form.get('artistName')
        song_album = request.form.get('albumName')
        song_album_image_url = request.form.get('albumImageURL')
        song_label = request.form.get('label')
        song_explicit = request.form.get('explicit')
        if song_explicit:
            song_explicit = "true"
        else:
            song_explicit = "false"
        song_duration = request.form.get('duration')
        song_track_URL = request.form.get('trackURL')
        song_popularity = request.form.get('popularity')
        song_danceability = request.form.get('danceability')
        song_energy = request.form.get('energy')
        song_loudness = request.form.get('loudness')
        song_speechiness = request.form.get('speechiness')
        song_acousticness = request.form.get('acousticness')
        song_instrumentalness = request.form.get('instrumentalness')
        song_liveness = request.form.get('liveness')
        song_happiness = request.form.get('happiness')

        album_name = request.form.get('album')
        album_artist = request.form.get('artist')
        album_ReleaseDate = request.form.get('albumReleaseDate')
        album_genres = request.form.get('genres')
        album_average_rating = request.form.get('averageRating')

        artist_name = request.form.get('name')
        artist_genre = request.form.get('genre')
        artist_facebook = request.form.get('facebook')
        artist_twitter = request.form.get('twitter')
        artist_website = request.form.get('website')
        artist_mtv = request.form.get('mtv')

        remove_song_title = request.form.get('remove_song_title')
        remove_song_artist = request.form.get('remove_song_artist')

        remove_album_title = request.form.get('remove_album_title')
        remove_album_artist = request.form.get('remove_album_artist')

        remove_artist_name = request.form.get('remove_artist_name')

        song_to_update = request.form.get('song_to_update')
        song_artist_to_update = request.form.get('song_artist_to_update')
        song_column = request.form.get('song_column')
        song_new_value = request.form.get('song_new_value')

        album_to_update = request.form.get('album_to_update')
        album_artist_to_update = request.form.get('album_artist_to_update')
        album_column = request.form.get('album_column')
        album_new_value = request.form.get('album_new_value')

        artist_to_update = request.form.get('artist_to_update')
        artist_column = request.form.get('artist_column')
        artist_new_value = request.form.get('artist_new_value')

        conn = sqlite3.connect('Music.db')
        cur = conn.cursor()

        try:
            if song_name:
                query = f'''INSERT INTO Song (Song, Artist, Album,
                    AlbumImageURL, TrackDuration, Explicit, Popularity, Danceability, Energy,
                    Loudness, Speechiness, Acousticness, Instrumentalness, Liveness, Valence, Label,
                    TrackURI) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                cur.execute(query, (song_name, song_artist, song_album, song_album_image_url,
                            song_duration, song_explicit, song_popularity, song_danceability,
                            song_energy, song_loudness, song_speechiness, song_acousticness,
                            song_instrumentalness, song_liveness, song_happiness, song_label, song_track_URL))
                flash("Successfully inserted record.", category="success")
            elif album_name:
                query = f'''INSERT INTO Album (Album, Artist, ReleaseDate, Genres,
                    AverageRating) VALUES (?, ?, ?, ?, ?)'''
                cur.execute(query, (album_name, album_artist,
                            album_ReleaseDate, album_genres, album_average_rating))
                flash("Successfully inserted record.", category="success")
            if artist_name:
                query = f'''INSERT INTO Artist (Artist, facebook, twitter, website, genre,
                    mtv) VALUES (?, ?, ?, ?, ?, ?)'''
                cur.execute(query, (artist_name, artist_facebook,
                            artist_twitter, artist_website, artist_genre, artist_mtv))
                flash("Successfully inserted record.", category="success")
            if remove_song_title:
                query = f'''DELETE FROM Song WHERE Song = ? AND Artist = ?'''
                cur.execute(query, (remove_song_title, remove_song_artist))
                flash("Successfully deleted record.", category="success")
            if remove_album_title:
                query = '''DELETE FROM Album Where Album = ? AND Artist = ?'''
                cur.execute(query, (remove_album_title, remove_album_artist))
                flash("Successfully deleted record.", category="success")
            if remove_artist_name:
                query = f'''DELETE FROM Artist WHERE Artist = ?'''
                cur.execute(query, (remove_artist_name,))
                flash("Successfully deleted record.", category="success")
            if song_to_update:
                query = f'''UPDATE Song SET {song_column} = "{
                    song_new_value}" WHERE Song = "{song_to_update}" AND Artist = "{song_artist_to_update}"'''
                cur.execute(query)
                flash("Successfully updated record.", category="success")
            if album_to_update:
                query = f'''UPDATE Album SET {album_column} = "{
                    album_new_value}" WHERE Album = "{album_to_update}" AND Artist = "{album_artist_to_update}"'''
                cur.execute(query)
                flash("Successfully updated record.", category="success")
            if artist_to_update:
                query = f'''UPDATE Artist SET {artist_column} = "{
                    artist_new_value}" WHERE name = "{artist_to_update}"'''
                cur.execute(query)
                flash("Successfully updated record.", category="success")
        except Exception:
            flash(f"Error: Something went wrong.", category="error")
            return render_template('change.html')

        conn.commit()
        cur.close()
        conn.close()

        return render_template("change.html")
    else:
        return render_template("change.html")
