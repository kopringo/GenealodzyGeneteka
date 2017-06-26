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


class Geneteka:
    """
    Class for geneteka.genealodzy.pl search engine
    """

    logger = logging.getLogger('gen')
    request_session = None
    options = {}

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

        # cache
        if self.options['cache']:
            if not os.path.exists('.cache'):
                self.logger.debug('No cache folder, mkdir')
                os.mkdir('.cache')

    def http_get(self, url, tries=3, cache_tag=None, cache=None, referer=None):
        """ http get request
            @param url: url to fetch
            @param tries: how many time we should try to get page
            @param cache_tag:
            @param cache:
        """
        self.logger.info(u'Fetching: %s [try=%s]', url, str(4-tries))

        if cache is not None:
            cache_tag = Geneteka.create_cache_tag(cache)

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
                return self.http_get(url, tries-1, cache_tag=cache_tag, cache=cache, referer=referer)
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

    def find_params_in_url(self, url):
        """ Find voivodeship in the url """

        self.logger.debug('Find params in url: %s', url)

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

    def fetch_main_index(self):
        """
        Fetch data from first page of the search engine
        """

        path = G_PATH1 % self.options['lastname']
        url = '%s://%s/%s' % (G_PROT, G_HOST, path)

        html_content = self.http_get(url)
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

                rid_w = self.find_params_in_url(url)
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

    def fetch_area(self, area, limit=1):
        """ Fetch single area """
        self.logger.debug('Fetch area: %s [l=%s]', area['url'], str(limit))

        # Check if the limit has been reached
        if limit == 0:
            self.logger.debug('Limit=0')
            return []

        area['url'] = 'http://geneteka.genealodzy.pl/api/getAct.php?draw=1&start=0&length=50&op=gt&lang=pol&search_lastname=%s&rid=%s&bdm=%s&w=%s' % (self.options['lastname'], area['rid'], area['rid'], area['wid'])
        referer = 'http://geneteka.genealodzy.pl/index.php?op=gt&lang=pol&search_lastname=%s&search_lastname2=&from_date=&to_date=&exac=&rid=%s&bdm=%s&w=%s' % (self.options['lastname'], area['rid'], area['rid'], area['wid'])

        html_content = self.http_get(area['url'], cache={'url': area['url'], 'count': str(area['count'])}, referer=referer)
        #try:
        #    tree = html.fromstring(html_content)
        #except Exception:  # as e
        #    pass
        #    # @todo

        # content of pages
        pages = []
        pages.append(html_content.strip())

        # looking for next pages
        pages_found = 0
        if limit > 1 and False:
            for link in tree.xpath('//a'):
                url = link.values()[0]
                if url.find('rpp1') > -1:
                    full_url = u'http://%s/%s' % (G_HOST, url)
                    h_content = self.http_get(full_url, cache={'url': full_url, 'count': str(area['count'])})
                    pages.append(h_content)

                    pages_found = pages_found + 1
                    if pages_found > limit:
                        break

        # parse rows
        rows = []
        """
        for page in pages:
            tree = html.fromstring(page)
            subhead = tree.xpath('//tr[@class="subhead"]')
            if len(subhead) == 0 or not subhead:
                subhead = tree.xpath('//tr[@class="head"]')

            if subhead and len(subhead) > 0:
                item = subhead[0]
                while item.getnext() is not None:
                    item = item.getnext()
                    row = self.parse_row(item, area['rid'])
                    if row is not None:
                        rows.append(row)
        print(pages)
        print(rows)
        sys.exit()
        """

        for page in pages:
            page_rows = json.loads(page)
            if isinstance(page_rows, dict):
                rows.extend(page_rows['data'])
        return rows

    def fetch_areas(self, areas):
        """ Fetch all areas """
        rows = []
        for area in areas:
            self.logger.info(u'Area: %s [rid=%s]', area['w'], area['rid'])
            a_data = self.fetch_area(area, self.options['limit'])
            rows.extend(a_data)
        return rows

    def find_titles(self, item):
        """ Find title """
        ret = []
        items = item.getchildren()
        for _item in items:
            ret.extend(self.find_titles(_item))
        if 'title' in item.attrib:
            ret.append(item.attrib['title'])
        return ret

    def find_hrefs(self, item):
        """ Find links """
        ret = []
        items = item.getchildren()
        for _item in items:
            ret.extend(self.find_hrefs(_item))
        if 'href' in item.attrib:
            ret.append(item.attrib['href'])
        return ret

    def parse_row(self, row, mode=''):
        """ Parse single row """
        if mode == 'B' or mode == 'D':
            items = row.getchildren()
            if len(items) < 9:
                return None
            note = self.find_titles(items[9])
            urls = self.find_hrefs(items[11])

            item = {
                'lp': items[0].text_content(),  # lp
                'year': items[1].text_content(),  # rok
                'doc': items[2].text_content(),  # akt
                'firstname': items[3].text_content(),  # imie
                'lastname': items[4].text_content(),  # nazw
                'father_firstname': items[5].text_content(),  # imie ojca
                'mother_firstname': items[6].text_content(),  # imie matki
                'mother_lastname': items[7].text_content(),  # nazw matki
                'parish': items[8].text_content(),  # parafia
                'note': note,  # uwagi
                'urls': urls  # skan
            }
            return item

        if mode == 'M':
            items = row.getchildren()
            if len(items) == 15:
                note = self.find_titles(items[12])
                urls = self.find_hrefs(items[14])

                item = {
                    'lp': items[0].text_content(),  # lp
                    'year': items[1].text_content(),  # rok
                    'doc': items[2].text_content(),  # akt

                    'firstname1': items[3].text_content(),  # imie
                    'lastname1': items[4].text_content(),  # nazw
                    'mother_lastname': items[5].text_content(),  # nazw matki
                    'parents1': self.find_titles(items[6]),

                    'firstname2': items[7].text_content(),  # imie
                    'lastname2': items[8].text_content(),  # nazw
                    'mother_lastname2': items[9].text_content(),  # nazw matki
                    'parents2': self.find_titles(items[10]),

                    'parish': items[11].text_content(),  # parafia
                    'note': note,  # uwagi
                    'urls': urls  # skan
                }
                return item
        return None


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

    return options


###############################################################################
# main function


def main(argv):
    """ Main function """
    options = parse_opts(argv)
    geneteka = Geneteka(options)
    data = geneteka.fetch_main_index()
    data2 = geneteka.fetch_areas(data)

if __name__ == "__main__":
    main(sys.argv[1:])
sys.exit()
