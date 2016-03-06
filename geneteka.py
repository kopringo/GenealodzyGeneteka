#!/usr/bin/env python

import sys
import os
import requests
from lxml import html

if len(sys.argv) == 1:
    print ('no params')
    print ('run: ./geneteka.py nazwisko')
    sys.exit(1)
    
lastname = sys.argv[1]

url = u'http://geneteka.genealodzy.pl/index.php?search_lastname=%s&search_lastname2=&from_date=&to_date=&rpp1=&bdm=&w=&op=se&lang=pol&exac=1' % lastname
page = requests.get(url)
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
    
    print url
    page = requests.get(url)
    if page.status_code != 200:
        print ('no 200 code [!]')
        return False
    
    tree = html.fromstring(page.text)
    
    if find_next_pages:
        for link in tree.xpath('//center/a'):
            url = link.values()[0]
            parse_list(u'http://geneteka.genealodzy.pl/%s' % url, mode, False)
            

parse_list(pages_b[0])
#print pages_b
#print pages_m
#print pages_d
        
    #print dir(link)
    
#print page.text