#!/usr/bin/env python

import os
import sys
import heapq
import signal
import logging
import datetime
from argparse import ArgumentParser
from getpass import getpass
from typing import List
from pixiv_down import utils

from pixiv_down.crawler import Crawler, Illust

# parse args
parser = ArgumentParser()

_download_types = [
    'iid',      # download illusts by illust id list
    'aid',      # download illusts by artist id list
    'tag',      # download illusts by tag name
    'rcmd',     # download illusts from recomments
    'related',  # download related illusts of the specified illust
    'ranking',  # download daily ranking of the specified day
]
parser.add_argument(dest='download_type', choices=_download_types,
                    help='The download type: iid / aid / tag / rcmd / related / ranking')

parser.add_argument(dest='args', nargs='*',
                    help=("The positional args for download type, "
                          "e.g., `illust ids` / `artist ids` / `tag names`"))

# bookmars and page count
parser.add_argument('-b', dest='min_bookmarks', default=3000, type=int,
                    help='The min bookmarks of illust (default: %(default)s)')
parser.add_argument('-c', dest='max_page_count', default=10, type=int,
                    help='The max page count of illust (default: %(default)s)')
parser.add_argument('-q', dest='min_quality', type=int,
                    help=('The min quality of illust, '
                          'the quality eauals the num of bookmarks per 100 views '
                          '(default: %(default)s)'))
parser.add_argument('-l', dest='max_sex_level', choices=[1, 2, 3], default=2, type=int,
                    help='The max sex level of illust (default: %(default)s)')
parser.add_argument('-n', dest='illust_num', default=300, type=int,
                    help='Total number of illusts to download (default: %(default)s)')

# download options
parser.add_argument('-k', dest='keep_json', action='store_true',
                    help='Keep the json result to files')
parser.add_argument('--show', dest='show_json', type=str,
                    help='Print the json result on stdout')
parser.add_argument('-p', dest='path', type=str, default='./',
                    help='The storage path of illusts (default: %(default)s)')
parser.add_argument('-r', dest='resolution', type=str,
                    help=('The resolution of illusts: s / m / l / o '
                          '(i.e., square / middle / large / origin, can set multiple)'))

# date interval
today = datetime.date.today()
parser.add_argument('-s', dest='start', type=str, default='2016-01-01',
                    help='The start date of illust for tag searching (default: `%(default)s`)')
parser.add_argument('-e', dest='end', type=str, default=today.isoformat(),
                    help='The end date of illust for tag searching (default: today)')

# only download the newest illusts on ranking
parser.add_argument('--only_new', action='store_true',
                    help='Only download the newest illusts from ranking')
parser.add_argument('--without_illust', action='store_true',
                    help="Don't download illusts when download ranking")

# log level
parser.add_argument('--log', dest='loglevel', type=str, default='warn',
                    choices=['debug', 'info', 'warn', 'error'],
                    help='The log level (default: `%(default)s`)')
args = parser.parse_args()


###############################################################################
#                               init the spider                               #
###############################################################################

# set logger
logging.basicConfig(format='[%(levelname)s] %(funcName)s: %(message)s')
loglevel = getattr(logging, args.loglevel.upper())
logging.root.setLevel(loglevel)

# parse illust resolution
if args.resolution:
    _img_types = {'s': 'square', 'm': 'medium', 'l': 'large', 'o': 'origin'}
    RESOLUTIONS = {v: True if k in args.resolution else False
                   for k, v in _img_types.items()}

# get the refresh_token
REFRESH_TOKEN = os.environ.get('PIXIV_TOKEN') or getpass('Please enter the refresh_token:')

# check the download path
if not os.path.isdir(args.path):
    print(f'`{args.path}` is not a directory.')
    sys.exit(1)
else:
    DOWNLOAD_DIR = os.path.join(args.path, 'pixdown')

# parse show_json option
if not args.show_json:
    JSON_FIELDS = []
else:
    JSON_FIELDS = args.show_json.split(',')

# login
crawler = Crawler(refresh_token=REFRESH_TOKEN, download_dir=DOWNLOAD_DIR)
user = crawler.login()
print('Login OK!\n')


################################################################################
#                                  downladers                                  #
################################################################################

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
            fetcher = crawler.ifetch_artist_artwork(aid,
                                                    args.keep_json, args.max_page_count,
                                                    args.min_bookmarks, args.min_quality,
                                                    args.max_sex_level)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  q={illust.quality}  total={n_crawls}')

                if JSON_FIELDS:
                    utils.print_json(illust, keys=JSON_FIELDS)
                    print('-' * 50, end='\n\n')

                if n_crawls >= args.illust_num:
                    break

            if args.resolution:
                crawler.multi_download(illusts, **RESOLUTIONS)


def download_illusts_by_tag():
    if not args.args:
        logging.error('not specified the tag name')
    else:
        for tag in args.args:
            print(f'scraping tag: {tag}')
            illusts: List[Illust] = []
            fetcher = crawler.ifetch_tag(tag, args.start, args.end,
                                         False, args.max_page_count,
                                         args.min_bookmarks, args.min_quality,
                                         args.max_sex_level)
            for n_crawls, illust in enumerate(fetcher, start=1):
                if len(illusts) < args.illust_num:
                    heapq.heappush(illusts, illust)
                else:
                    heapq.heappushpop(illusts, illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:4.1f}k  total={n_crawls}')

                if JSON_FIELDS:
                    utils.print_json(illust, keys=JSON_FIELDS)
                    print('-' * 50, end='\n\n')

            if args.keep_json:
                for illust in illusts:
                    jsonfile = crawler.dir_json_illust.joinpath(f'{illust.id}.json')
                    utils.save_jsonfile(illust, jsonfile.as_posix())

            if args.resolution:
                crawler.multi_download(illusts, **RESOLUTIONS)


def download_illusts_from_recommend():
    illusts: List[Illust] = []
    fetcher = crawler.ifetch_recommend(args.keep_json, args.max_page_count,
                                       args.min_bookmarks, args.min_quality,
                                       args.max_sex_level)
    for n_crawls, illust in enumerate(fetcher, start=1):
        illusts.append(illust)

        bk = illust.total_bookmarks / 1000
        print(f'iid={illust.id}  bookmark={bk:.1f}k  q={illust.quality}  total={n_crawls}')

        if JSON_FIELDS:
            utils.print_json(illust, keys=JSON_FIELDS)
            print('-' * 50, end='\n\n')

        if n_crawls >= args.illust_num:
            break

    if args.resolution:
        crawler.multi_download(illusts, **RESOLUTIONS)


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

            fetcher = crawler.ifetch_related(iid, args.keep_json, args.max_page_count,
                                             args.min_bookmarks, args.min_quality,
                                             args.max_sex_level)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  q={illust.quality}  total={n_crawls}')

                if JSON_FIELDS:
                    utils.print_json(illust, keys=JSON_FIELDS)
                    print('-' * 50, end='\n\n')

                if n_crawls >= args.illust_num:
                    break

            if args.resolution:
                crawler.multi_download(illusts, **RESOLUTIONS)


def download_illusts_by_id():
    if not args.args:
        logging.error('not specified the illust id list')
    else:
        total = len(args.args)
        illusts: List[Illust] = []
        for n_crawls, iid in enumerate(args.args, start=1):
            try:
                iid = int(iid)
                illust = crawler.fetch_illust(iid, args.keep_json)
            except (TypeError, ValueError) as e:
                print(e)
                continue
            else:
                if not illust or not illust['visible']:
                    print(f'not found: id={iid}')
                    continue
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  q={illust.quality}  progress: {n_crawls} / {total}')

                if JSON_FIELDS:
                    utils.print_json(illust, keys=JSON_FIELDS)
                    print('-' * 50, end='\n\n')

        if args.resolution:
            crawler.multi_download(illusts, **RESOLUTIONS)


def iget_days():
    for date in args.args:
        if ',' in date:
            start, end = date.split(',')
            try:
                start = datetime.date.fromisoformat(start)
                end = datetime.date.fromisoformat(end)
            except ValueError:
                continue

            while start <= end:
                yield start
                start += datetime.timedelta(1)
        else:
            try:
                yield datetime.date.fromisoformat(date)
            except ValueError:
                pass


def download_illust_from_ranking():
    for date in iget_days():
        if args.without_illust:
            crawler.fetch_web_ranking(date, args.keep_json)
        else:
            illusts: List[Illust] = []
            fetcher = crawler.ifetch_ranking(date, args.only_new,
                                             args.keep_json, args.max_page_count,
                                             args.min_bookmarks, args.min_quality,
                                             args.max_sex_level)
            for n_crawls, illust in enumerate(fetcher, start=1):
                illusts.append(illust)

                bk = illust.total_bookmarks / 1000
                print(f'iid={illust.id}  bookmark={bk:.1f}k  q={illust.quality}  progress: {n_crawls}')

                if JSON_FIELDS:
                    utils.print_json(illust, keys=JSON_FIELDS)
                    print('-' * 50, end='\n\n')

            if args.resolution:
                crawler.multi_download(illusts, **RESOLUTIONS)
        print(f'Ranking {date} finished')


def signal_hander(*_):
    print('\nUser exit')
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_hander)

    if args.download_type == 'iid':
        # NOTE: 此模式下，会忽略 min_bookmarks，max_page_count，top，max_crawl 四个限制条件
        download_illusts_by_id()
        print('============== illusts fetched ==============\n\n')

    elif args.download_type == 'aid':
        download_illusts_by_artist()
        print('============== artist works fetched ==============\n\n')

    elif args.download_type == 'tag':
        download_illusts_by_tag()
        print('============== tag fetched ==============\n\n')

    elif args.download_type == 'rcmd':
        download_illusts_from_recommend()
        print('============== recommend fetched ==============\n\n')

    elif args.download_type == 'related':
        download_illusts_by_related()
        print('============== related fetched ==============\n\n')

    elif args.download_type == 'ranking':
        download_illust_from_ranking()
        print('============== ranking fetched ==============\n\n')

    else:
        print('wrong type')
        sys.exit(1)


if __name__ == '__main__':
    main()
