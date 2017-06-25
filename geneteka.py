#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import requests
import getopt
import logging
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

        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

    def http_get(self, url, tries=3):
        self.logger.info(u'Fetching: %s [try=%s]' % (url, str(4-tries)))

        page = self.request_session.get(url)
        if page.status_code != 200:
            if tries > 0:
                time.sleep(1000)
                return self.http_get(url, tries-1)
            else:
                raise 'http exception'
        return page.text

    def find_params_in_url(self, url):
        """ Find voivodeship in the url """

        self.logger.debug('Find params in url: %s' % url)

        rid = None
        w = None

        o = urlparse(url)
        query = parse_qs(o.query)
        if 'w' in query and query['w'][0] in G_VV:
            w = G_VV[query['w'][0]]

        if 'rid' in query:
            rid = query['rid'][0]

        return {'rid': rid, 'w': w}

    def fetch_main_index(self):
        """
        Fetch data from first page of the search engine
        """

        PATH = G_PATH1 % self.options['lastname']
        url = '%s://%s/%s' % (G_PROT, G_HOST, PATH)

        html_content = self.http_get(url)
        try:
            tree = html.fromstring(html_content)
        except:
            pass
            # @todo

        pages_b = []
        pages_m = []
        pages_d = []

        for link in tree.xpath('//td[@class="gt"]/a'):

            ilosc = 0
            try:
                ilosc = int(link.text_content().strip())
            except:
                pass

            if ilosc > 0:
                url = link.values()[0]
                count = int(link.text_content().strip())

                rid_w = self.find_params_in_url(url)
                self.logger.info(u'%s %s %s' % (rid_w['w'], rid_w['rid'], str(count)))

                area = {
                    'url': u'http://geneteka.genealodzy.pl/%s' % url,
                    'rid': rid_w['rid'],
                    'w': rid_w['w']
                }

                if rid_w['rid'] == 'B':
                    pages_b.append(area)
                if rid_w['rid'] == 'D':
                    pages_d.append(area)
                if rid_w['rid'] == 'S':
                    pages_m.append(area)

        return {
            'b': pages_b,
            'm': pages_m,
            'd': pages_d
        }

    def fetch_area(self, area, limit=1):
        self.logger.debug('Fetch area: %s [l=%s]' % (area['url'], str(limit)))

        # Check if the limit has been reached
        if limit == 0:
            self.logger.debug('Limit=0')
            return

        html_content = self.http_get(area['url'])
        try:
            tree = html.fromstring(html_content)
        except:
            pass
            # @todo

        # content of pages
        pages = []
        pages.append(html_content)

        # looking for next pages
        pages = []
        pages_found = 0
        if limit > 1:
            for link in tree.xpath('//a'):
                url = link.values()[0]
                if url.find('rpp1') > -1:
                    h_content = self.http_get(u'http://%s/%s' % (G_HOST, url))
                    pages.append(h_content)

                    pages_found = pages_found + 1
                    if pages_found > limit:
                        break

        # parse rows
        items = []
        for page in pages:
            tree = html.fromstring(page)
            subhead = tree.xpath('//tr[@class="subhead"]')
            if not subhead or len(subhead) == 0:
                subhead = tree.xpath('//tr[@class="head"]')

            if subhead and len(subhead) > 0:
                item = subhead[0]
                while item.getnext() is not None:
                    item = item.getnext()
                    r = self.parse_row(item, area['rid'])
                    if r is not None:
                        items.append(r)
        return items

    def fetch_areas(self, areas):
        rows = []
        for area in areas:
            self.logger.info(u'Area: %s [rid=%s]' % (area['w'], area['rid']))
            a_data = self.fetch_area(area, self.options['limit'])
            rows.extend(a_data)
        return rows

    def find_titles(self, item):
        r = []
        items = item.getchildren()
        for _item in items:
            _r = self.find_titles(_item)
            r.extend(_r)
        if 'title' in item.attrib:
            r.append(item.attrib['title'])
        return r

    def find_hrefs(self, item):
        r = []
        items = item.getchildren()
        for _item in items:
            _r = self.find_hrefs(_item)
            r.extend(_r)
        if 'href' in item.attrib:
            r.append(item.attrib['href'])
        return r

    def parse_row(self, row, mode=''):
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
        'debug': False
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
            except:
                options['limit'] = 3
        elif opt in ("-d"):
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
    options = parse_opts(argv)
    g = Geneteka(options)
    data = g.fetch_main_index()
    data2 = g.fetch_areas(data)

if __name__ == "__main__":
    main(sys.argv[1:])
sys.exit()


"""
b_items = []
d_items = []
m_items = []
for k in pages_b:
    b_items.extend(parse_list(k, 'B'))
for k in pages_d:
    d_items.extend(parse_list(k, 'D'))
for k in pages_m:
    m_items.extend(parse_list(k, 'M'))

for item in b_items:
    print('B;', item['year'], item['doc'], item['firstname'], item['lastname'], item['parish'])
for item in d_items:
    print('D;', item['year'], item['doc'], item['firstname'], item['lastname'], item['parish'])
for item in m_items:
    print('M;', item['year'], item['doc'], item['firstname1'], item['lastname1'], item['firstname2'], item['lastname2'], item['parish'])


for i in pages_b:
    parse_list(i, 'B')
for i in pages_m:
    parse_list(i, 'M')
for i in pages_d:
    parse_list(i, 'D')
"""
