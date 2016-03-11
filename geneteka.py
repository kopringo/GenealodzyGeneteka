#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import codecs
import requests
from lxml import html

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

if len(sys.argv) == 1:
    print ('no params')
    print ('run: ./geneteka.py nazwisko')
    sys.exit(1)
    
lastname = sys.argv[1]

s = requests.Session()

url = u'http://geneteka.genealodzy.pl/index.php?search_lastname=%s&search_lastname2=&from_date=&to_date=&rpp1=&bdm=&w=&op=se&lang=pol&exac=1' % lastname
page = s.get(url)
if page.status_code != 200:
    print ('no 200 code')
    sys.exit(1)

tree = html.fromstring(page.text)

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
        count = link.text_content()
        print count, url
        
        if url.find('rid=B') > -1:
            pages_b.append(u'http://geneteka.genealodzy.pl/%s' % url)
        if url.find('rid=D') > -1:
            pages_d.append(u'http://geneteka.genealodzy.pl/%s' % url)
        if url.find('rid=S') > -1:
            pages_m.append(u'http://geneteka.genealodzy.pl/%s' % url)

def find_titles(item):
    
    r = []
    
    items = item.getchildren()
    for _item in items:
        _r = find_titles(_item)
        r.extend(_r)
    
    if 'title' in item.attrib:
        r.append(item.attrib['title'])
    
    return r

def find_hrefs(item):
    
    r = []
    
    items = item.getchildren()
    for _item in items:
        _r = find_hrefs(_item)
        r.extend(_r)
    
    if 'href' in item.attrib:
        r.append(item.attrib['href'])
    
    return r

def parse_row(row, mode=''):
    if mode == 'B' or mode == 'D':
        
        items = row.getchildren()
        if len(items) < 9:
            return None
        note = find_titles(items[9])
        urls = find_hrefs(items[11])
        
        item = {
            'lp': items[0].text_content(), # lp
            'year': items[1].text_content(), # rok
            'doc': items[2].text_content(), # akt
            'firstname': items[3].text_content(), # imie
            'lastname': items[4].text_content(), # nazw
            'father_firstname': items[5].text_content(), # imie ojca
            'mother_firstname': items[6].text_content(), # imie matki
            'mother_lastname': items[7].text_content(), # nazw matki
            'parish': items[8].text_content(), # parafia
            'note': note, # uwagi
            'urls': urls # skan
        }
        
        return item
        
    if mode == 'M':
        
        items = row.getchildren()
        if len(items) == 15:
            note = find_titles(items[12])
            urls = find_hrefs(items[14])
            
            item = {
                'lp': items[0].text_content(), # lp
                'year': items[1].text_content(), # rok
                'doc': items[2].text_content(), # akt
                
                'firstname1': items[3].text_content(), # imie
                'lastname1': items[4].text_content(), # nazw
                'mother_lastname': items[5].text_content(), # nazw matki
                'parents1': find_titles(items[6]),
                
                'firstname2': items[7].text_content(), # imie
                'lastname2': items[8].text_content(), # nazw
                'mother_lastname2': items[9].text_content(), # nazw matki
                'parents2': find_titles(items[10]),
                
                'parish': items[11].text_content(), # parafia
                'note': note, # uwagi
                'urls': urls # skan
            }
            
            return item
        
    return None
    

def parse_list(url, mode='', find_next_pages=True):
    
    global s
    
    time.sleep(0.5)
    page = s.get(url)
    if page.status_code != 200:
        print ('no 200 code [!]')
        return False
    
    items = []
    
    tree = html.fromstring(page.text)
    
    if find_next_pages:
        for link in tree.xpath('//a'):
            url = link.values()[0]
            if url.find('rpp1') > -1:
                items.extend( parse_list(u'http://geneteka.genealodzy.pl/%s' % url, mode, False) )
    
    subhead = tree.xpath('//tr[@class="subhead"]')
    if not subhead or len(subhead) == 0:
        subhead = tree.xpath('//tr[@class="head"]')
    
    
    
    if subhead and len(subhead) > 0:
        item = subhead[0]
        while item.getnext() is not None:
            item = item.getnext()
            r = parse_row(item, mode)
            if r is not None:
                items.append(r)
            
    return items

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
    print 'B;', item['year'], item['doc'], item['firstname'], item['lastname'], item['parish']
for item in d_items:
    print 'D;', item['year'], item['doc'], item['firstname'], item['lastname'], item['parish']
for item in m_items:
    print 'M;', item['year'], item['doc'], item['firstname1'], item['lastname1'], item['firstname2'], item['lastname2'], item['parish']

"""
for i in pages_b:
    parse_list(i, 'B')
for i in pages_m:
    parse_list(i, 'M')
for i in pages_d:
    parse_list(i, 'D')
"""

