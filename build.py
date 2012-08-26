import urllib2
import sqlite3
import codecs
import os
import re
import time
import datetime
from operator import itemgetter
from bs4 import BeautifulSoup

requestCount = 0

def getHTML(url):
	global requestCount
	requestCount = requestCount + 1
	if requestCount % 10 == 0:
		time.sleep(1)
	opener = urllib2.build_opener()
	opener.addheaders = [('User-agent', 'Mozilla/5.0')]
	file = opener.open(url)
	content = file.read()
	file.close()
	return content

def sortFriendly(name):
	name = name.lower()
	if name.startswith('the '):
		return name[4:]
	if name.startswith('a '):
		return name[2:]
	if name.startswith('an '):
		return name[3:]
	return name

def initializeArtist(dbConnection,artistQuery):
	artist_search_cache = []
	artists = []
	artists_albums = []
	albums = []
	albums_tracks = []
	tracks = []
	cursor = dbConnection.cursor()
	cursor.execute('SELECT artist_uri FROM artist_search_cache WHERE artist_query LIKE "' + artistQuery + '"')
	result = cursor.fetchone()
	if result:
		return result['artist_uri']
	# not already cached, we need to request it from Spotify
	xml = getHTML('http://ws.spotify.com/search/1/artist?q='+artistQuery)
	documentSoup = BeautifulSoup(xml,'xml')
	artistTag = documentSoup.artist
	if not artistTag:
		return ''
	artistName = artistTag.find('name').string
	artistURI = artistTag.get('href')
	if artistURI == '':
		return ''
	# cache it up and save the artist info in the database
	artist_search_cache.append((artistQuery, artistURI))
	artists.append((artistURI, artistName, sortFriendly(artistName)))
	# get the list of albums for the artist
	xml = getHTML('http://ws.spotify.com/lookup/1/?uri='+artistURI+'&extras=albumdetail')
	documentSoup = BeautifulSoup(xml,'xml')
	albumList = documentSoup.findAll('album')
	for albumTag in albumList:
		# check that it's available in the US
		territories = albumTag.availability.territories.string
		if not territories or not (('US' in territories) or ('worldwide' in territories)):
			continue
		albumName = albumTag.find('name').string
		albumArtist = albumTag.artist.find('name').string
		try:
			albumYear = int(albumTag.released.string)
		except:
			albumYear = 0
		albumURI = albumTag.get('href')
		if albumURI == '':
			continue
		albums.append((albumURI, albumName, albumArtist, albumYear))
		artists_albums.append((artistURI, albumURI))
		# get the list of tracks for an album
		xml = getHTML('http://ws.spotify.com/lookup/1/?uri='+albumURI+'&extras=trackdetail')
		documentSoup = BeautifulSoup(xml,'xml')
		trackList = documentSoup.findAll('track')
		for trackTag in trackList:
			trackArtist = trackTag.artist.get('href')
			if trackArtist != artistURI:
				continue
			trackName = trackTag.find('name').string
			trackURI = trackTag.get('href')
			if trackURI == '':
				continue
			trackDisc = trackTag.find('disc-number').string
			try:
				trackNumber = int(trackTag.find('track-number').string)
			except:
				trackNumber = 0
			try:
				trackLength = int(float(trackTag.find('length').string))
			except:
				trackLength = 0
			tracks.append((trackURI, trackName, trackNumber, trackLength))
			albums_tracks.append((albumURI, trackURI, trackDisc))
	with dbConnection:
		cursor.executemany('INSERT INTO artist_search_cache VALUES(?,?)', artist_search_cache)
		cursor.executemany('INSERT INTO artists VALUES(?,?,?)', artists)
		cursor.executemany('INSERT INTO albums VALUES(?,?,?,?)', albums)
		cursor.executemany('INSERT INTO artists_albums VALUES(?,?)', artists_albums)
		cursor.executemany('INSERT INTO tracks VALUES(?,?,?,?)', tracks)
		cursor.executemany('INSERT INTO albums_tracks VALUES(?,?,?)', albums_tracks)
	return artistURI

def initializeArtists(dbConnection,artistsPath,artistURIs):
	print 'Reading artists from file...'
	artists = []
	artistsFile = open(artistsPath,'r')
	for artist in artistsFile:
		artist = artist.split('\n')[0].replace(' ','%20')  # chop off the newline, encode the spaces
		artists.append(artist)
	currentCount = 0
	artistCount = len(artists)
	for artist in artists:
		currentCount = currentCount + 1
		print ' '+str(currentCount)+' of '+str(artistCount)+' ('+str(round(100*float(currentCount)/float(artistCount),2))+'%)'
		artistURI = initializeArtist(dbConnection,artist)
		if artistURI == '':
			continue
		artistURIs.append(artistURI)
	return

def getArtistsFromFile(artistsPath,artists):
	print 'Reading artists from file...'
	artists = []
	artistsFile = open(artistsPath,'r')
	for artist in artistsFile:
		artist = artist.split('\n')[0].replace(' ','%20')  # chop off the newline, encode the spaces
		artists.append(artist)
	currentCount = 0
	artistCount = len(artists)
	for artist in artists:
		currentCount = currentCount + 1
		print ' '+str(currentCount)+' of '+str(artistCount)+' ('+str(round(100*float(currentCount)/float(artistCount),2))+'%)'
		# get the artist's spotify URI
		xml = getHTML('http://ws.spotify.com/search/1/artist?q='+artist)
		documentSoup = BeautifulSoup(xml,'xml')
		artistTag = documentSoup.artist
		artistName = artistTag.find('name').string
		artistURI = artistTag.get('href')
		if artistURI == '':
			continue
		artistObject = { 'name': artistName, 'URI': artistURI, 'albums': [] }
		# get the list of albums for an artist
		xml = getHTML('http://ws.spotify.com/lookup/1/?uri='+artistURI+'&extras=albumdetail')
		documentSoup = BeautifulSoup(xml,'xml')
		albumList = documentSoup.findAll('album')
		for albumTag in albumList:
			territories = albumTag.availability.territories.string
			if not territories or not ('US' in territories):
				continue
			albumName = albumTag.find('name').string
			albumArtist = albumTag.artist.find('name').string
			albumYear = albumTag.released.string
			albumURI = albumTag.get('href')
			if albumURI == '':
				continue
			albumObject = { 'name': albumName, 'artist': albumArtist, 'year': albumYear, 'URI': albumURI, 'discs': [] }
			# get the list of tracks for an album
			xml = getHTML('http://ws.spotify.com/lookup/1/?uri='+albumURI+'&extras=trackdetail')
			documentSoup = BeautifulSoup(xml,'xml')
			trackList = documentSoup.findAll('track')
			for trackTag in trackList:
				trackArtist = trackTag.artist.get('href')
				if trackArtist != artistURI:
					continue
				trackName = trackTag.find('name').string
				trackURI = trackTag.get('href')
				if trackURI == '':
					continue
				trackDisc = trackTag.find('disc-number').string
				trackNumber = trackTag.find('track-number').string
				trackLength = trackTag.find('length').string
				trackObject = { 'name': trackName, 'URI': trackURI, 'number': trackNumber, 'duration': trackLength }
				for discObject in albumObject['discs']:
					if discObject['number'] == trackDisc:
						break
				else:
					discObject = {'number': trackDisc, 'tracks': [] }
					albumObject['discs'].append(discObject)
				discObject['tracks'].append(trackObject)
			artistObject['albums'].append(albumObject)
		artists.append(artistObject)
	artistsFile.close()
	return

def outputHeader(outputBuffer):
	outputBuffer.write('<!DOCTYPE html><html><head><title>Spotify Browser</title>')
	outputBuffer.write('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">')
	outputBuffer.write('<meta name="viewport" content="width=device-width, initial-scale=1">')
	outputBuffer.write('<link rel="stylesheet" href="//code.jquery.com/mobile/1.1.1/jquery.mobile-1.1.1.min.css">')
	outputBuffer.write('<script src="//code.jquery.com/jquery-1.7.1.min.js"></script>')
	outputBuffer.write('<script src="//code.jquery.com/mobile/1.1.1/jquery.mobile-1.1.1.min.js"></script>')
	outputBuffer.write('</head><body>')
	return

def writeListHeader(outputBuffer,id,title,buttonTarget,buttonText):
	outputBuffer.append('<div data-role="page" data-add-back-btn="true" id="'+id+'">')
	outputBuffer.append('<div data-role="header" data-position="fixed"><h1>'+title+'</h1>')
	if len(buttonText) > 0:
		outputBuffer.append('<a href="'+buttonTarget+'" data-icon="arrow-r" data-iconpos="right" class="ui-btn-right">'+buttonText+'</a>')
	outputBuffer.append('</div><div data-role="content">')
	outputBuffer.append('<ul data-role="listview">')
	return

def writeListSeparator(outputBuffer,title):
	outputBuffer.append('<li data-role="list-divider">'+title+'</li>')
	return

def writeListItem(outputBuffer,title,subtitle,target,count):
	outputBuffer.append('<li><a href="'+target+'">')
	if len(title) > 0:
		outputBuffer.append('<h3>'+title+'</h3>')
	if len(subtitle) > 0:
		outputBuffer.append('<p>'+subtitle+'</p>')
	if len(count) > 0:
		outputBuffer.append('<span class="ui-li-count">'+count+'</span>')
	outputBuffer.append('</a></li>')
	return

def writeListClosure(outputBuffer):
	outputBuffer.append('</ul>')
	outputBuffer.append('</div></div>')
	return

def outputArtistsFromDB(dbConnection,outputFile,artistURIs):
	artistBuffer = []
	albumBuffer = []
	cursor = dbConnection.cursor()
	queryLines = []
	queryLines.append('SELECT * FROM artists WHERE 1=0')
	for artistURI in artistURIs:
		queryLines.append(' OR artist_uri LIKE "' + artistURI + '"')
	queryLines.append(' ORDER BY artist_sort_name ASC')
	cursor.execute(''.join(queryLines))
	artists = cursor.fetchall()
	writeListHeader(artistBuffer,'artists','Artists', '', '')
	currentLetter = ''
	for artist in artists:
		cursor.execute('SELECT albums.* FROM artists_albums LEFT JOIN albums ON artists_albums.album_uri=albums.album_uri WHERE artists_albums.artist_uri LIKE "' + artist['artist_uri'] + '"')
		albums = cursor.fetchall()
		if len(albums) == 0:
			continue
		if currentLetter != artist['artist_sort_name'][0]:
			writeListSeparator(artistBuffer, artist['artist_sort_name'][0].upper())
			currentLetter = artist['artist_sort_name'][0]
		writeListItem(artistBuffer, artist['artist_name'], '', '#'+artist['artist_uri'], str(len(albums)))
		outputAlbumsFromDB(dbConnection,albumBuffer,artist,albums)
	writeListClosure(artistBuffer)
	artistBuffer.append(u''.join(albumBuffer))
	outputFile.write(u''.join(artistBuffer))
	return

def outputAlbumsFromDB(dbConnection,albumBuffer,artist,albums):
	trackBuffer = []
	cursor = dbConnection.cursor()
	writeListHeader(albumBuffer, artist['artist_uri'], artist['artist_name'], artist['artist_uri'], 'Launch Artist')
	for album in albums:
		cursor.execute('SELECT albums_tracks.disc_name, tracks.* FROM albums_tracks LEFT JOIN tracks ON albums_tracks.track_uri=tracks.track_uri WHERE albums_tracks.album_uri LIKE "' + album['album_uri'] + '" ORDER BY albums_tracks.disc_name ASC, tracks.track_number ASC ')
		tracks = cursor.fetchall()
		if len(tracks) == 0:
			continue
		writeListItem(albumBuffer, album['album_name'] + ' (' + str(album['album_year']) + ')', album['album_artist'], '#'+album['album_uri'], str(len(tracks)))
		outputTracksFromDB(trackBuffer,album,tracks)
	writeListClosure(albumBuffer)
	albumBuffer.append(u''.join(trackBuffer))
	return

def outputTracksFromDB(trackBuffer,album,tracks):
	writeListHeader(trackBuffer, album['album_uri'], album['album_name'], album['album_uri'], 'Launch Album')
	currentDisc = ''
	for track in tracks:
		try:
			minutes = track['track_length'] / 60
			seconds = track['track_length'] % 60
			if seconds < 10:
				padding = '0'
			else:
				padding = ''
			duration = str(minutes) + ':' + padding + str(seconds)
		except:
			duration = ""
		if currentDisc != track['disc_name']:
			writeListSeparator(trackBuffer, 'Disc ' + track['disc_name'])
			currentDisc = track['disc_name']
		writeListItem(trackBuffer, str(track['track_number']) + '. ' + track['track_name'], '', track['track_uri'], duration)
	writeListClosure(trackBuffer)
	return

def outputArtists(outputFile,artists):
	albumOutput = []
	outputFile.write('<div data-role="page" data-add-back-btn="true" id="artists">')
	outputFile.write('<div data-role="header"><h1>Artists</h1></div><div data-role="content"><ul data-role="listview">')
	sortedArtists = sorted(artists,key=itemgetter('name'))
	currentLetter = ''
	for artist in sortedArtists:
		if currentLetter != artist['name'][0]:
			outputFile.write('<li data-role="list-divider">'+artist['name'][0]+'</li>')
		outputOneArtist(outputFile,artist)
		outputAlbums(albumOutput,artist)
	outputFile.write('</ul></div></div>')
	outputFile.write(''.join(albumOutput))
	return

def outputOneArtist(outputFile,artist):
	outputFile.write('<li><a href="#'+artist['URI']+'">'+artist['name'])
	outputFile.write('<span class="ui-li-count">'+str(len(artist['albums']))+'</span></a></li>')
	return

def outputAlbums(albumOutput,artist):
	trackOutput = []
	albumOutput.append('<div data-role="page" data-add-back-btn="true" id="'+artist['URI']+'">')
	albumOutput.append('<div data-role="header"><h1>'+artist['name']+'</h1><a href="'+artist['URI']+'" data-icon="arrow-r" data-iconpos="right" class="ui-btn-right">Launch Artist</a></div>')
	albumOutput.append('<div data-role="content"><ul data-role="listview">')
	for album in artist['albums']:
		outputOneAlbum(albumOutput,album)
		outputTracks(trackOutput,album)
	albumOutput.append('</ul></div></div>')
	albumOutput.append(''.join(trackOutput))
	return

def outputOneAlbum(albumOutput,album):
	count = 0
	for disc in album['discs']:
		count += len(disc['tracks'])
	if count==0:
		return
	albumOutput.append('<li><a href="#'+album['URI']+'"><h3>'+album['name']+'</h3><p>'+album['artist']+'</p>')
	albumOutput.append('<span class="ui-li-count">'+str(count)+'</span></a></li>')
	return

def outputTracks(trackOutput,album):
	trackOutput.append('<div data-role="page" data-add-back-btn="true" id="'+album['URI']+'">')
	trackOutput.append('<div data-role="header"><h1>'+album['name']+'</h1><a href="'+album['URI']+'" data-icon="arrow-r" data-iconpos="right" class="ui-btn-right">Launch Album</a></div>')
	trackOutput.append('<div data-role="content"><ol data-role="listview">')
	isSingleDisc= (len(album['discs']) == 1)
	for disc in album['discs']:
		if not isSingleDisc:
			trackOutput.append('<li data-role="list-divider">Disc '+disc['number']+'</li>')
		for track in disc['tracks']:
			outputOneTrack(trackOutput,track)
	trackOutput.append('</ol></div></div>')
	return

def outputOneTrack(trackOutput,track):
	trackOutput.append('<li><a data-ajax="false" href="'+track['URI']+'">'+track['name'])
	try:
		minutes = int(float(track['track_length'])) / 60
		seconds = int(float(track['track_length'])) % 60
		if seconds < 10:
			padding = '0'
		else:
			padding = ''
		duration = str(minutes) + ':' + padding + str(seconds)
	except:
		duration = ""
	if len(duration) > 0:
		trackOutput.append('<span class="ui-li-count">'+duration+'</span>')
	trackOutput.append('</a></li>')
	return

def outputHTML(dbConnection,outputPath,artistURIs):
	outputFile = codecs.open(outputPath,'w', 'utf-8')
	outputHeader(outputFile)
	outputArtistsFromDB(dbConnection,outputFile,artistURIs)
	outputFile.write('</body></html>')
	outputFile.close()
	return

def openDBConnection():
	if os.path.exists('build/spotify.db'):
		conn = sqlite3.connect('build/spotify.db')
		conn.row_factory = sqlite3.Row
		return conn
	# create the database using the defined schema
	conn = sqlite3.connect('build/spotify.db')
	conn.row_factory = sqlite3.Row
	cursor = conn.cursor()
	schemaFile = open('build/spotify-schema.sql','r')
	for command in schemaFile:
		command = command.split('\n')[0]  # chop off the newline
		cursor.execute(command)
	conn.commit()
	schemaFile.close()
	return conn

def closeDBConnection(dbConnection):
	dbConnection.commit()
	dbConnection.cursor().close()
	return

def main():
	artistURIs = []
	albumURIs = []
	trackURIs = []
	dbConnection = openDBConnection()
	#getArtistsFromFile('config/artists.txt',artists)
	initializeArtists(dbConnection,'config/artists.txt',artistURIs)
	outputHTML(dbConnection,'publish/index.html',artistURIs)
	closeDBConnection(dbConnection)
	return

main()