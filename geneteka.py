#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import getopt
import logging
import hashlib
import requests

from lxml import html
from abc import abstractmethod
# from pip._vendor.distlib.locators import HTML_CONTENT_TYPE

try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs


# sys.stdout = codecs.getwriter('utf8')(sys.stdout)

###############################################################################

G_PROT = 'http'
G_HOST = 'geneteka.genealodzy.pl'
G_PATH1 = 'index.php?search_lastname=%s&search_lastname2=&from_date=&to_date=&rpp1=&bdm=&w=&op=se&lang=pol&exac=1'
G_VV = {
    '01ds': 'dolnośląskie',
    '02kp': 'kujawsko-pomorskie',
    '03lb': 'lubelskie',
    '04ls': 'lubuskie',
    '05ld': 'łódzkie',
    '06mp': 'małopolskie',
    '07mz': 'mazowieckie',
    '71wa': 'Warszawa',
    '08op': 'opolskie',
    '09pk': 'podkarpackie',
    '10pl': 'podlaskie',
    '11pm': 'pomorskie',
    '12sl': 'śląskie',
    '13sk': 'świętokrzyskie',
    '14wm': 'warmińsko-mazurskie',
    '15wp': 'wielkopolskie',
    '16zp': 'zachodniopomorskie',
    '21uk': 'Ukraina',
    '22br': 'Białoruś',
    '23lt': 'Litwa',
    '25po': 'Pozostałe'
}


class HttpClient:
    """ Http Client with cache support """

    logger = None
    request_session = None

    def __init__(self, logger, options):
        self.logger = logger
        self.request_session = requests.Session()
        
        # cache
        if options['cache']:
            if not os.path.exists('.cache'):
                self.logger.debug('No cache folder, mkdir')
                os.mkdir('.cache')

    def http_get(self, url, tries=3, cache=None, cache_tag=None, referer=None):
        """ http get request
            @param url: url to fetch
            @param tries: how many time we should try to get page
            @param cache_tag:
            @param cache:
        """
        self.logger.info(u'Fetching: %s [try=%s]', url, str(4-tries))

        if cache is not None:
            cache_tag = HttpClient.create_cache_tag(cache)

        # read from cache
        if cache_tag is not None:
            cache_file = '.cache/%s' % cache_tag
            if os.path.exists(cache_file):
                self.logger.debug('Return from cache')
                return open(cache_file, 'r').read()
            # print(cache_tag)
            # sys.exit()

        # download page
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        if referer:
            headers['Referer'] = referer
        page = self.request_session.get(url, headers=headers)
        if page.status_code != 200:
            if tries > 0:
                time.sleep(1000)
                return self.http_get(url, tries-1, cache=cache, cache_tag=cache_tag, referer=referer)
            else:
                raise 'http exception'

        data = page.text

        # write to cache
        if cache_tag:
            cache_file = '.cache/%s' % cache_tag
            open(cache_file, 'w').write(data)

        return data

    @classmethod
    def create_cache_tag(cls, key):
        """ Create a cache hash based on array data"""
        hash_engine = hashlib.sha1()
        if isinstance(key, str):
            hash_engine.update(key)
        if isinstance(key, dict):
            hash_key = str(u'__'.join(sorted(key.values()))).encode('utf-8')
            hash_engine.update(hash_key)
        return hash_engine.hexdigest()

    @staticmethod
    def find_params_in_url(url):
        """ Find voivodeship in the url """

        # self.logger.debug('Find params in url: %s', url)

        rid = None
        wid = None
        wname = None

        url_parsed = urlparse(url)
        query = parse_qs(url_parsed.query)
        if 'w' in query:
            wid = query['w'][0]
            if query['w'][0] in G_VV:
                wname = G_VV[query['w'][0]]

        if 'rid' in query:
            rid = query['rid'][0]

        return {'rid': rid, 'w': wname, 'wid': wid}


class Geneteka:
    """
    Class for geneteka.genealodzy.pl search engine
    """

    logger = logging.getLogger('gen')
    request_session = None
    options = {}
    http_client = None

    def __init__(self, options):
        self.request_session = requests.Session()
        self.options = options

        # logging
        level = logging.INFO
        if self.options['debug']:
            level = logging.DEBUG
        self.logger.setLevel(level)

        # logging handler (console)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

        self.http_client = HttpClient(self.logger, self.options)

    def fetch_main_index(self):
        """
        Fetch data from first page of the search engine
        """

        path = G_PATH1 % self.options['lastname']
        url = '%s://%s/%s' % (G_PROT, G_HOST, path)

        html_content = self.http_client.http_get(url)
        try:
            tree = html.fromstring(html_content)
        except:  #  Exception as e
            pass
            # @todo

        pages = []

        for link in tree.xpath('//td[@class="gt"]/a'):

            ilosc = 0
            try:
                ilosc = int(link.text_content().strip())
            except Exception:  # as e
                pass

            if ilosc > 0:
                url = link.values()[0]
                count = int(link.text_content().strip())

                rid_w = HttpClient.find_params_in_url(url)
                self.logger.info(u'%s %s %s', rid_w['w'], rid_w['rid'], str(count))

                area = {
                    'url': u'http://geneteka.genealodzy.pl/%s' % url,
                    'rid': rid_w['rid'],
                    'w': rid_w['w'],
                    'wid': rid_w['wid'],
                    'count': count,
                }
                pages.append(area)

        return pages

    def fetch_area(self, area, start=0, limit=50, http_limit=3):
        """ Fetch single area
            @param area: 
            @param start: records offset
            @param limit: records limit to fetch
            @param http_limit: how many times we should try to get data
            @return: list of records
        """
        self.logger.debug('Fetch area: %s [l=%s]', area['url'], str(limit))

        # Check if the limit has been reached
        if http_limit == 0:
            self.logger.debug('http_limit=0')
            return []

        area['url'] = 'http://geneteka.genealodzy.pl/api/getAct.php?draw=1&start=%s&length=%s&op=gt&lang=pol&search_lastname=%s&rid=%s&bdm=%s&w=%s' % (str(start), str(limit), self.options['lastname'], area['rid'], area['rid'], area['wid'])
        referer = 'http://geneteka.genealodzy.pl/index.php?op=gt&lang=pol&search_lastname=%s&search_lastname2=&from_date=&to_date=&exac=&rid=%s&bdm=%s&w=%s' % (self.options['lastname'], area['rid'], area['rid'], area['wid'])

        html_content = self.http_client.http_get(area['url'], cache={'url': area['url'], 'count': str(area['count']), 'start': str(start)}, referer=referer)

        page_rows = json.loads(html_content)
        if isinstance(page_rows, dict):
            return page_rows['data']

    def fetch_areas(self, areas):
        """ Fetch all areas """

        for area in areas:
            self.logger.info(u'Area: %s [rid=%s] [count=%d]', area['w'], area['rid'], area['count'] )
            page = 0
            rows = []
            while page < self.options['limit'] and page*50 < area['count']:

                a_data = self.fetch_area(area, page*50, 50)
                rows.extend(a_data)
                page = page + 1

            # parse data
            parser = Geneteka.Parser(area['rid'])
            area['rows'] = parser.parse(rows)

    class AbstractRow:
        row_type = None
        year = None
        a_number = None
        notes = []
        parish = None
        place = None

        def __init__(self, row, row_type=None):
            self.row_type = row_type
            self.year = row[0]
            self.a_number = row[1]

        @abstractmethod
        def __str__(self):
            raise NotImplementedError()

    class RowBirth(AbstractRow):
        firstname = None
        lastname = None
        father_firstname = None
        mother_firstname = None
        mother_lastname = None

        def __init__(self, row, row_type='B'):
            super(Geneteka.RowBirth, self).__init__(row, row_type)
            self.firstname = row[2]
            self.lastname = row[3]
            self.father_firstname = row[4]
            self.mother_firstname = row[5]
            self.mother_lastname = row[6]

            self.parish = row[7]
            self.place = row[8]
            if row[9]:
                self.notes.append(row[9])

        def __str__(self):
            return u'B %s %s | %s %s' % ( str(self.year), str(self.a_number), self.firstname, self.lastname)

    class RowDeath(RowBirth):
        """ Death row """

        def __init__(self, row):
            super(Geneteka.RowDeath, self).__init__(row, 'D')

        def __str__(self):
            return u'D %s %s | %s %s' % ( str(self.year), str(self.a_number), self.firstname, self.lastname)

    class RowMariage(AbstractRow):
        """ Marriage row """
        m_firstname = None
        m_lastname = None
        m_parents = None
        f_firstname = None
        f_lastname = None
        f_parent = None

        def __init__(self, row):
            super(Geneteka.RowMariage, self).__init__(row, 'M')
            self.m_firstname = row[2]
            self.m_lastname = row[3]
            self.m_parents = row[4]
            self.f_firstname = row[5]
            self.f_lastname = row[6]
            self.f_parents = row[7]
            self.parish = row[8]
            if row[9]:
                self.notes.append(row[9])

        def __str__(self):
            return u'M %s %s | %s %s | %s %s' % ( str(self.year), str(self.a_number), self.m_firstname, self.m_lastname, self.f_firstname, self.f_lastname)

    class Parser:
        row_type = None
        row_class = None

        def __init__(self, row_type):
            self.row_type = row_type
            if row_type == 'B':
                self.row_class = Geneteka.RowBirth
            elif row_type == 'D':
                self.row_class = Geneteka.RowDeath
            elif row_type in ['S', 'M']:
                self.row_class = Geneteka.RowMariage
            else:
                raise RuntimeError('Wrong type')

        def parse(self, rows):
            objects = []
            for row in rows:
                obj = self.row_class(row)
                objects.append(obj)
            return objects


def parse_opts_help():
    """ Print help for geneteka.py """
    print(u'geneteka.py [-d] [-l <limit>] [-o <outputfile>] <lastname>')


def parse_opts(argv):
    """ Parse command line options """
    options = {
        'limit': 3,  # limit fo pages to fetch in a single area
        'output': None,
        'lastname': None,
        'debug': False,
        'cache': True
    }
    try:
        opts, args = getopt.getopt(argv, "dhl:o:", ["limit=", "output="])
    except getopt.GetoptError:
        parse_opts_help()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            parse_opts_help()
            sys.exit()
        elif opt in ("-l", "--limit"):
            try:
                options['limit'] = int(arg)
            except Exception:  # as e
                options['limit'] = 3
        elif opt in ("-d", ):
            options['debug'] = True
        elif opt in ("-o", "--output"):
            options['output'] = arg

    if options['limit'] > 7:
        options['limit'] = 3

    if len(args) > 0:
        options['lastname'] = args[0]

    if options['lastname'] is None:
        print("Please provide lastname")
        parse_opts_help()
        sys.exit(1)

    return options


###############################################################################
# main function


def main(argv):
    """ Main function """
    options = parse_opts(argv)

    geneteka = Geneteka(options)
    data = geneteka.fetch_main_index()
    geneteka.fetch_areas(data)

    for area in data:
        for row in area['rows']:
            print(row)

if __name__ == "__main__":
    main(sys.argv[1:])
sys.exit()
