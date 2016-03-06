#!/usr/bin/env python

import sys
import os
import time
import requests
from lxml import html

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

def parse_list(url, mode='', find_next_pages=True):
    
    global s
    
    print '----'
    time.sleep(0.5)
    page = s.get(url)
    if page.status_code != 200:
        print ('no 200 code [!]')
        return False
    
    tree = html.fromstring(page.text)
    
    if find_next_pages:
        for link in tree.xpath('//a'):
            url = link.values()[0]
            if url.find('rpp1') > -1:
                parse_list(u'http://geneteka.genealodzy.pl/%s' % url, mode, False)
    
    subhead = tree.xpath('//tr[@class="subhead"]')
    if not subhead or len(subhead) == 0:
        subhead = tree.xpath('//tr[@class="head"]')
        
    if subhead and len(subhead) > 0:
        item = subhead[0]
        while item.getnext() is not None:
            item = item.getnext()
            print item.text_content()

for i in pages_b:
    parse_list(i)
for i in pages_m:
    parse_list(i)
for i in pages_d:
    parse_list(i)
        
    #print dir(link)
    
#print page.text