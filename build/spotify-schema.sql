CREATE TABLE artist_search_cache(artist_query varchar(100) PRIMARY KEY ON CONFLICT IGNORE, artist_uri varchar(100));
CREATE TABLE artists(artist_uri varchar(100) PRIMARY KEY ON CONFLICT IGNORE, artist_name varchar(100), artist_sort_name varchar(100));
CREATE TABLE artists_albums(artist_uri varchar(100), album_uri varchar(100), PRIMARY KEY(artist_uri, album_uri) ON CONFLICT IGNORE);
CREATE TABLE albums(album_uri varchar(100) PRIMARY KEY ON CONFLICT IGNORE, album_name varchar(100), album_artist varchar(100), album_year int);
CREATE TABLE albums_tracks(album_uri varchar(100), track_uri varchar(100), disc_name varchar(100), PRIMARY KEY(album_uri, track_uri) ON CONFLICT IGNORE);
CREATE TABLE tracks(track_uri varchar(100) PRIMARY KEY ON CONFLICT IGNORE, track_name varchar(100), track_number int, track_length int);
