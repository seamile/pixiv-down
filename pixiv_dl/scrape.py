#!/usr/bin/env python

import os
import sys

import logging
from argparse import ArgumentParser
from getpass import getpass
from typing import List

from spider import Crawler, Illust

# parse args
parser = ArgumentParser()

scrape_types = [
    'iid',         # download illusts by illust id list
    'aid',        # download illusts by artist id list
    'tag',        # download illusts by tag name
    'rcmd',       # download illusts from recomments
    'related',    # download related illusts of the specified illust
]
parser.add_argument(dest='scrape_type', choices=scrape_types, help='the scrape type')
parser.add_argument(dest='args', nargs='*',
                    help="the follow args for scrape type, exp. e.g., `tag name` or `illust id list`.")

# bookmars and img count
parser.add_argument('-b', dest='min_bookmarks', default=3000, type=int,
                    help='the min bookmarks of illust. (default: %(default)s)')
parser.add_argument('-c', dest='max_img_count', default=10, type=int,
                    help='the max img count of one illust. (default: %(default)s)')
parser.add_argument('-t', dest='total_crawls', default=300, type=int,
                    help='the total illusts of crawls. (default: %(default)s)')

# download options
parser.add_argument('-p', dest='path', type=str, default='./',
                    help='the storage path (default: `%(default)s`)')
parser.add_argument('-d', dest='download', type=str,
                    help=('download types: s/m/l/o. '
                          'means that: square/middle/large/origin. '
                          'can set multiple.'))
parser.add_argument('-k', dest='keep_json', action='store_true', help='keep json files')


parser.add_argument('-e', dest='earliest', type=str, default='2016-01-01',
                    help='the earliest date of illust with a tag (default: `%(default)s`)')

# log level
parser.add_argument('-l', dest='loglevel', type=str, default='warn',
                    choices=['debug', 'info', 'warn', 'error'],
                    help='the log level (default: `%(default)s`)')
args = parser.parse_args()


###############################################################################
#                               init the spider                               #
###############################################################################

# set logger
logging.basicConfig(format='[%(levelname)s] %(funcName)s: %(message)s')
loglevel = getattr(logging, args.loglevel.upper())
logging.root.setLevel(loglevel)

# parse download types
if args.download:
    IMG_TYPES = {'s': 'square', 'm': 'medium', 'l': 'large', 'o': 'origin'}
    download_types = {v: True if k in args.download else False
                      for k, v in IMG_TYPES.items()}

# get the refresh_token
refresh_token = os.environ.get('PIXIV_TOKEN') or getpass('Please enter the refresh_token:')

# check the download path
if not os.path.isdir(args.path):
    print(f'`{args.path}` is not a directory.')
    sys.exit(1)
else:
    download_dir = os.path.join(args.path, 'pixiv-down')

# login
crawler = Crawler(refresh_token=refresh_token, download_dir=download_dir)
user = crawler.login()
print('Login OK!\n')


def download_illusts_by_artist():
    if not args.args:
        logging.error('not specified the illust id list')
    else:
        for aid in args.args:
            try:
                aid = int(aid)
            except (TypeError, ValueError):
                print(f'wrong artist id: {aid}')
                continue

            illusts: List[Illust] = []
            fetcher = crawler.ifetch_artist_artwork(int(aid),
                                                    args.keep_json,
                                                    args.max_img_count,
                                                    args.min_bookmarks)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  total={n_crawls}')

                if n_crawls >= args.total_crawls:
                    break

            if args.download:
                crawler.multi_download(illusts, **download_types)


def download_illusts_by_tag():
    if not args.args:
        logging.error('not specified the tag name')
    else:
        for tag in args.args:
            print(f'scraping tag: {tag}')
            illusts: List[Illust] = []
            fetcher = crawler.ifetch_tag(tag, args.earliest,
                                         args.keep_json, args.max_img_count, args.min_bookmarks)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  total={n_crawls}')

                if n_crawls >= args.total_crawls:
                    break

            if args.download:
                crawler.multi_download(illusts, **download_types)


def download_illusts_from_recommend():
    illusts: List[Illust] = []
    fetcher = crawler.ifetch_recommend(args.keep_json, args.max_img_count, args.min_bookmarks)
    for n_crawls, illust in enumerate(fetcher, start=1):
        illusts.append(illust)

        bk = illust.total_bookmarks / 1000
        print(f'iid={illust.id}  bookmark={bk:.1f}k  total={n_crawls}')

        if n_crawls >= args.total_crawls:
            break

    if args.download:
        crawler.multi_download(illusts, **download_types)


def download_illusts_by_related():
    if not args.args:
        logging.error('not specified the related illust id')
    else:
        for iid in args.args:
            illusts: List[Illust] = []
            try:
                iid = int(iid)
            except (TypeError, ValueError):
                print(f'wrong illust id: {iid}')
                continue

            fetcher = crawler.ifetch_related(iid, args.keep_json, args.max_img_count, args.min_bookmarks)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  total={n_crawls}')

                if n_crawls >= args.total_crawls:
                    break

            if args.download:
                crawler.multi_download(illusts.values(), **download_types)


def download_illusts_by_id():
    if not args.args:
        logging.error('not specified the illust id list')
    else:
        total = len(args.args)
        for n_crawls, iid in enumerate(args.args, start=1):
            try:
                iid = int(iid)
            except (TypeError, ValueError):
                print(f'wrong illust id: {iid}')
                continue
            else:
                illust = crawler.fetch_illust(iid, args.keep_json)
                crawler.download_illust(illust, **download_types)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  progress: {n_crawls} / {total}')


if args.scrape_type == 'aid':
    download_illusts_by_artist()
    print('============== artist works fetched ==============\n\n')

elif args.scrape_type == 'tag':
    download_illusts_by_tag()
    print('============== tag fetched ==============\n\n')

elif args.scrape_type == 'rcmd':
    download_illusts_from_recommend()
    print('============== recommend fetched ==============\n\n')

elif args.scrape_type == 'related':
    download_illusts_by_related()
    print('============== related fetched ==============\n\n')

elif args.scrape_type == 'iid':
    # NOTE: 此模式下，会忽略 min_bookmarks，max_img_count，top，max_crawl 四个限制条件
    download_illusts_by_id()
    print('============== illusts fetched ==============\n\n')
else:
    print('wrong type')
    sys.exit(1)
