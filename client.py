#!/usr/bin/python3
import traceback
import sys
from colorama import Fore, Back, Style

import argparse, sys
import random
import requests
import asyncio
import requests
import math
import json
import queries
import time

from turfpy.transformation import transform_translate
from sanic import Sanic
from sanic.response import text
from cors import add_cors_headers
from options import setup_options

#####################################################################################

#handle arguments
parser = argparse.ArgumentParser()
parser.add_argument("--cli", help="don't run server, just reverse-geocode a pair of coordinates", action="store_true", default=False)
parser.add_argument("--no_expiration", help="cached excerpt don't expire", action="store_true", default=False)
parser.add_argument("--mes", help="URL to the map-excerpt server", default="http://localhost:8080/cacheArea")

args=parser.parse_args()
args = vars(args)

CLI = args["cli"]
NO_EXPIRATION = args["no_expiration"]
if NO_EXPIRATION and not CLI:
    print("expiration deactivated")

'''
TODO: implement non-geojson option
'''

async def mainCLI():
    #get user input coordinates
    #coordsTest = (51.96555344223404, 7.625174736813619) #Bergstraße 50
    span = 125

    #if arguments were used
    startTime = time.time()

    coordsTest = (float(sys.argv[1]), float(sys.argv[2]))
    print(f'reverse-geocoding {coordsTest}...')
        
    #cache = MapCache(testdata)

    if not cache.areaIsValid(coordsTest):
        data = await excerptServer.fetchExcerptObscured(coordsTest, span)
        cache.cacheExcerpt(data, coordsTest, span)
        
    print(cache.returnNearestPlace(coordsTest))
    endTime = time.time()

    #print(f'query took {endTime-startTime} seconds')


class MapCache:
    '''
    initString: put data in there in case you wanna initialise the cache with anything.
    json: whether the object assumes that it works with geojson from the excerpt-server.
    ttl: time-to-live of a cached excerpt in seconds.
    '''
    def __init__(self, conn, initString=None, geojson=None, ttl=None):
        if initString == None:
            initString = '''{
                    "type": "FeatureCollection",
                    "features": [
                    ]
                }'''
        if geojson == None:
            geojson == True
        if ttl == None:
            ttl = 604800
            
        self.db = self.getConnection(conn)
        self.cache = json.loads(initString)
        self.geojson = json
        self.ttl = ttl

        self.initialiseDB()
        return

    def __str__(self):
        if self.geojson:
            return json.dumps(self.cache)
        else:
            #TODO: when efficient version happens
            return
    
    def getConnection(self, args):
        database=args["database"]
        user=args["user"]
        password=args["password"]
        host=args["host"]
        port=args["port"]
        print()
        try:
            session = queries.Session(f"postgresql://{user}:{password}@{host}:{port}/{database}")
            print(session)
            return session
            
        except:
            return False

    def initialiseDB(self):
        map_cache = f'''
        CREATE TABLE IF NOT EXISTS map_cache (
            id serial PRIMARY KEY, 
            place_name varchar, 
            geom geometry(Point, 4326),
            expiration bigint,
            place_id int UNIQUE,
            area_id int,

            CONSTRAINT area_id
                FOREIGN KEY(area_id) REFERENCES cached_area(area_id)
        );
        '''
        cached_area = f'''
        CREATE TABLE IF NOT EXISTS cached_area (
            area_id serial PRIMARY KEY UNIQUE,
            expiration bigint,
            geom geometry(Polygon, 4326)
        )
        '''
        cur = self.db.query(cached_area)
        cur = self.db.query(map_cache)


    '''
    Stores a geojson feature collection in the cache-DB
    Feature collection must only contain points
    center: (lat, lon) tuple
    span: square-side-length / 2 in m
    '''
    def cacheExcerpt(self, inputString, coords, span=200):
        if self.geojson:
            try:
                data = json.loads(inputString)
                areaID = self.insertCacheRecord(coords, span)
                self.insertAddresses(data, areaID)    
                return self.cache
            except Exception as error:
                print("caching of excerpt goofed")
                print(error)
                print(traceback.format_exc())
                print(type(inputString))
                print(inputString)

        else:
            #TODO: this will take care of the more efficient json-like responses
            #       implement later.
            return

    '''
    TODO: (low priority) make SQL securer
    '''
    def insertAddresses(self, geojson, areaID):
        #prepare points for sql insertion
        points = []
        expirationTime = int(time.time()) + self.ttl
        
        for feature in geojson["features"]:
            coords = (feature["geometry"]["coordinates"][1],feature["geometry"]["coordinates"][0])
            placename = feature["properties"]["place"]
            placeID = feature["properties"]["place_id"]
            point = (str(placename), coords[1], coords[0], str(expirationTime), str(placeID), str(areaID))
            #point = f'(\'{placename}\', ST_Point({coords[1]},{coords[0]},4326), {str(expirationTime)}, {str(placeID)}, {str(areaID)})'
            points.append(point)

        #guarding clause. no reason to do anything if the place is empty.
        if len(points) < 1:
            return

        try: 
            conn = self.db
            #prepare the SQL statement

            arguments = []
            for p in points:
                arguments.append(f"(\'{p[0]}\',ST_Point({p[1]},{p[2]},4326),{p[3]},{p[4]},{p[5]})")
            args_str = ','.join(arguments)


            sql = f'''
            INSERT INTO map_cache 
                (place_name, geom, expiration, place_id, area_id) 
            VALUES {args_str}
            ON CONFLICT (place_id) DO UPDATE SET
                geom = EXCLUDED.geom,
                place_name = EXCLUDED.place_name,
                expiration = EXCLUDED.expiration,
                area_id = EXCLUDED.area_id
            WHERE map_cache.expiration > extract(epoch from now());'''

            #insert the data
            conn.query(sql)
        except (Exception) as error:
            print(error)
            print(traceback.format_exc())
        return

    '''
    inserts the cache record into the cached_area table
    returns the id of the inserted record.
    center: (lat, lon) tuple
    span: square-side-length / 2 in m
    '''
    def insertCacheRecord(self, center, span):
        expirationTime = int(time.time()) + self.ttl
        nW = self.offsetCoords(center, span, -span)
        sE = self.offsetCoords(center, -span, span)
        envelope = f'ST_MakeEnvelope({nW[1]}, {sE[0]}, {sE[1]}, {nW[0]}, 4326)'
        sql = f'''
        INSERT INTO cached_area
            (geom, expiration)
        VALUES 
            ({envelope}, {expirationTime})
        RETURNING
            area_id;
        '''
        
        #insert the data
        inserted = None
        try: 
            conn = self.db
            data = conn.query(sql)
            inserted = data[0].get("area_id")
        except (Exception) as error:
            print(error)
            print(traceback.format_exc())
        return inserted

    '''
    returns the address string of the point nearest to the asked-for location
    takes tuple of (lat, lon) coordinates
    '''
    def returnNearestPlace(self, location):
        expirationGuard = "AND expiration > extract(epoch from now()) "
        if NO_EXPIRATION:
            expirationGuard = ""

        sql = f'''
        SELECT 
            place_name,
            ST_Distance(geom, ST_MakePoint({location[1]},{location[0]},4326)::geography) AS dist
        FROM
            map_cache
        WHERE
            ST_DWithin(geom, ST_MakePoint({location[1]},{location[0]},4326)::geography, 500)
            {expirationGuard}
        ORDER BY dist ASC 
        LIMIT 10;
        '''
        try:
            conn = self.db
            data = conn.query(sql)
            print(data[0])
            if len(data) == 0:
                return "no address found"
        except (Exception) as error:
            print(error)
            print(traceback.format_exc())
        return data[0].get("place_name")

    '''
    takes (lat,lon) tuple
    returns area_id if area found, else False
    '''
    def areaIsValid(self, location):
        expirationGuard = "AND expiration > extract(epoch from now()) "
        if NO_EXPIRATION:
            expirationGuard = ""

        point = f'ST_MakePoint({location[1]},{location[0]},4326)::geography'
        sql = f'''
        SELECT
            area_id,
            expiration,
            geom
        FROM
            cached_area
        WHERE
            geom && {point}
            {expirationGuard}
        ORDER BY expiration DESC
        LIMIT 1;
        '''
        

        result = False
        try:
            conn = self.db
            data = conn.query(sql)
            
            if len(data) > 0:
                result = data[0].get("area_id", value=False)
        except (Exception) as error:
            print(error)
            print(traceback.format_exc())
        return result

    '''
    implementation of haversine distance in meters
    points are (lat,lon) WGS84
    used this solution: https://stackoverflow.com/a/4913653
    TODO: sometimes this is making a into very tiny negative floats.
    always -4.4013392767879984e-12. causes math domain error
    This seems to happen when the points are very close to each other. 
    a duplicate *math.sin(dlon/2) may have been the cause. UNLESS this shows up again-
    '''
    def getDistance(self, p1, p2):
        earthRadius = 6371000 #meters
        dlon = p2[1] - p1[1]
        dlat = p2[0] - p1[0]
        a = math.sin(dlat/2)**2 + math.cos(p1[0]) * math.cos(p2[0]) * math.sin(dlon/2)**2
        c = None
        try:
            c = 2 * math.asin(math.sqrt(a))
        except:
            print("a:")
            print(a)
            print("dlat, dlon:")
            print(f'{dlat}  {dlon}')
            print("p1, p2")
            print(f'{p1}  {p2}')
        distance = c*earthRadius
        return distance

    '''
    offset coords by e meters to the east and n meters towards north.
    returns new coordinate tuple (lat,lon)
    credit: https://stackoverflow.com/a/7478827
    '''
    def offsetCoords(self,coords, n, e):        
        
        #use turfpy
        geojson = f'{{"geometry": {{"coordinates": [{coords[1]},{coords[0]}],"type": "Point"}},"properties": {{}},"type": "Feature"}}'
        feature = json.loads(geojson)
        #north
        offsetFeature = transform_translate(feature, n, direction=365, mutate=True, units="m")
        #east
        offsetFeature = transform_translate(feature, e, direction=90, mutate=True, units="m")

        coords = (offsetFeature["geometry"]["coordinates"][1],offsetFeature["geometry"]["coordinates"][0])
        return coords

        '''
        lat = coords[0]
        lon = coords[1]
        r_earth = 6371000

        newLat = lat + (n / r_earth) * (180 / math.pi)
        newLon = lon + (e / r_earth) * (180 / math.pi) / math.cos(lat * math.pi/180)
        return (newLat, newLon)
        '''


class Communicator:
    '''
    initString: put data in there in case you wanna initialise the cache with anything.
    json: whether the object assumes that it works with geojson from the excerpt-server.
    '''
    def __init__(self, resourceURL):
        self.resourceURL = resourceURL
        return

    '''
    coords: (lat,lon) WGS84 tuple
    span: "radius" of map excerpt. half the side length of the cached square in meters
    '''
    async def fetchExcerpt(self, coords, span, format="json"):
        queryString = f"{self.resourceURL}?format={format}&polygon_geojson=1&lat={coords[0]}&lon={coords[1]}&span={span}"
        
        response = requests.get(queryString)
        #if format=="json":
        #    response = json.loads(response.text)
        
        return response.text

    '''
    wrapper of fetchExcerpt, that randomizes the coordinates for the request to the server
    within the given span.
    '''
    async def fetchExcerptObscured(self, coords, span, format="json"):
        coordsObscured = self.obscure(coords, span)

        excerpt = await self.fetchExcerpt(coordsObscured, span, format="json")
        return excerpt

    def obscure(self, coords, span):
        #simple random point, uniform.
        'TODO: implement more modes of random point selection'
        eastRandomOffset = random.uniform(-span, span)
        northRandomOffset = random.uniform(-span, span)
        coordsObscured = self.offsetCoords(coords, northRandomOffset, eastRandomOffset)
        return coordsObscured

    '''
    offset coords by e meters to the east and n meters towards north.
    returns new coordinate tuple (lat,lon)
    credit: https://stackoverflow.com/a/7478827
    '''
    def offsetCoords(self,coords, n, e):        
        
        #use turfpy
        geojson = f'{{"geometry": {{"coordinates": [{coords[1]},{coords[0]}],"type": "Point"}},"properties": {{}},"type": "Feature"}}'
        feature = json.loads(geojson)
        #north
        offsetFeature = transform_translate(feature, n, direction=365, mutate=True, units="m")
        #east
        offsetFeature = transform_translate(feature, e, direction=90, mutate=True, units="m")

        coords = (offsetFeature["geometry"]["coordinates"][1],offsetFeature["geometry"]["coordinates"][0])
        return coords

        '''
        lat = coords[0]
        lon = coords[1]
        r_earth = 6371000

        newLat = lat + (n / r_earth) * (180 / math.pi)
        newLon = lon + (e / r_earth) * (180 / math.pi) / math.cos(lat * math.pi/180)
        return (newLat, newLon)
        '''

'''
caches the map material at random dummy locations all across the globe
TODO: (low priority) avoid the ocean
TODO: (low priority) simulate trajectories
'''
async def cacheDummies(amount, comm, cache, span=200, minlat = -90, maxlat = 90, minlon = -180, maxlon = 180):
    for i in range(amount):
        lat = random.uniform(minlat, maxlat)
        lon = random.uniform(minlon, maxlon)
        print(f"caching dummy at {lat}, {lon}")
        coords = (lat, lon)
        data = await comm.fetchExcerpt(coords, span)
        cache.cacheExcerpt(data, coords, span)

############################################################
# start the server
############################################################

app = Sanic("mapExcerptServer")

@app.get("/status")
def status(request):
    return text("client mockup running")

@app.get("/reverse")
async def reverse(request):
    #get arguments
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))
    coords = (lat, lon)
    format = request.args.get("format")
    span = request.args.get("span") if request.args.get("span") else 200

    cacheValid = cache.areaIsValid(coords)

    #obfuscation by hiding the true query in the pile of the dummies
    dummyAmount = 0
    dummySplit = random.randint(0,dummyAmount)
    #for testing purposes, restrict to germany
    minlat, minlon = 46.9786, 5.5324
    maxlat, maxlon = 55.0903, 15.1561

    #get data and cache it, if no valid data is cached
    if not cacheValid:
        print(Fore.RED + "area not cached. caching"+ Style.RESET_ALL)

        #cache dummies
        await cacheDummies(dummySplit, excerptServer, cache, span, minlat, maxlat, minlon, maxlon)
        data = await excerptServer.fetchExcerptObscured(coords, span)
        cache.cacheExcerpt(data, coords, span)

        #cache more dummies so you can't just rely on last index.
        await cacheDummies(dummyAmount - dummySplit, excerptServer, cache, span, minlat, maxlat, minlon, maxlon)
    else:
        #await cacheDummies(1, excerptServer, cache, span)
        print(Fore.GREEN + "area is cached. searching cache."+Style.RESET_ALL)

    #reverse geocode from cache and return result
    result = cache.returnNearestPlace(coords)

    try:
        return text(result)
    except:
        print(type(result))

@app.get("/license")
def license(request):
    return text("Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright")

@app.get("/attribution")
def attribution(request):
    return license(request)

app.register_listener(setup_options, "before_server_start")
app.register_middleware(add_cors_headers, "response")

cacheDB = {
    "database":"cache",
    "user":"cache",
    "password":"cache1234",
    "host":"127.0.0.1",
    "port":5440
}



if __name__ == "__main__":
    #if arguments were used
    #if len (sys.argv) ==4:
    #    #this is to test
    #    print("testing")
        
    print("Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright")

    if CLI: #cli reverse-geocoding
        asyncio.run(mainCLI())
    else: #listen on port for rgc requests
        app.run(host='127.0.0.1', port=8081, access_log=True)

#Hacky way of specifying MES-URL
cacheAreaUrl = None
excerptServer= None

excerptServer = Communicator(args["mes"]) 

cache = MapCache(cacheDB, ttl=30)