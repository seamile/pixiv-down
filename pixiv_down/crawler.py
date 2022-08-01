import datetime
import json
import logging
import random
import time
from functools import wraps
from pathlib import Path
from typing import Iterable, Optional

import requests
from pixivpy3.aapi import AppPixivAPI
from pixivpy3.utils import JsonDict

from pixiv_down import utils as ut


class IllustFilter:
    def __init__(self,
                 max_count: int = 10,
                 min_bookmarks: int = 1000,
                 min_quality: Optional[float] = None,
                 sex_level: int = 2,
                 skip_aids: Iterable[int] = (),
                 skip_iids: Iterable[int] = ()):
        self.max_count = max_count
        self.min_bookmarks = min_bookmarks
        self.min_quality = min_quality
        self.sex_level = sex_level
        self.skip_aids = skip_aids
        self.skip_iids = skip_iids


class User(JsonDict):
    pass


class Illust(JsonDict):
    '''重写 __lt__ 方法，使 Illust keyi 进行排序'''

    @property
    def quality(self):
        '''质量'''
        if not self.visible:
            return -1
        elif not self.total_view:
            return 0
        else:
            return round(self.total_bookmarks / self.total_view * 100, 2)

    def is_qualified(self, ifilter: IllustFilter) -> bool:
        '''检查质量是否合格'''
        if not self.visible:
            logging.debug(f"skip Illust({self.id}): visible is {self.visible}")
            return False

        if self.type != 'illust':
            logging.debug(f"skip Illust({self.id}): type is {self.type}")
            return False
        if self.page_count > ifilter.max_count:
            logging.debug(f"skip Illust({self.id}): img_count is {self.page_count}")
            return False
        if self.total_bookmarks < ifilter.min_bookmarks:
            logging.debug(f"skip Illust({self.id}): bookmarks is {self.total_bookmarks}")
            return False
        if ifilter.min_quality and self.quality < ifilter.min_quality:
            logging.debug(f"skip Illust({self.id}): quality is {self.quality}")
            return False

        # 检查 sex_level 范围
        if ifilter.sex_level not in [1, 2, 3]:
            ifilter.sex_level = 2
        # 过滤 sex_level
        if ifilter.sex_level < 3 and self.x_restrict > 0:
            logging.debug(f"skip Illust({self.id}): x_restrict={self.x_restrict}")
            return False
        if ifilter.sex_level == 2 and self.sanity_level > 4:
            logging.debug(f"skip Illust({self.id}): sanity_level={self.sanity_level}")
            return False
        if ifilter.sex_level == 1 and self.sanity_level > 2:
            logging.debug(f"skip Illust({self.id}): sanity_level={self.sanity_level}")
            return False

        if self.user.id in ifilter.skip_aids or self.id in ifilter.skip_iids:
            logging.debug(f"skip Illust({self.id}): skip aid or iid")
            return False

        return True

    def __lt__(self, other: 'Illust'):
        if self.total_bookmarks == other.total_bookmarks:
            return self.quality < other.quality
        else:
            return self.total_bookmarks < other.total_bookmarks


class NeedRetry(Exception):
    pass


class OffsetLimit(Exception):
    pass


@ut.singleton
class Crawler:
    def __init__(self,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 refresh_token: Optional[str] = None,
                 download_dir: Optional[str] = None,
                 ifilter: IllustFilter = IllustFilter()):

        self.username = username
        self.password = password
        self.refresh_token = refresh_token
        self.base_dir = Path(download_dir or '').absolute()
        self.make_download_dirs()
        self.ifilter = ifilter

        self.api = AppPixivAPI()
        self.api.set_accept_language('zh-cn')
        self.decorate_apis_with_retry()

    @property
    def user(self) -> User:
        if not hasattr(self, '_user'):
            result = self.login()
            self._user = User(result['user'])
        return self._user

    @user.setter
    def user(self, user: User):
        self._user = user

    def make_download_dirs(self):
        dir_tree = {
            'json': ['illust', 'user', 'ranking'],
            'img': ['square', 'medium', 'large', 'origin', 'avatar']
        }
        self.base_dir.mkdir(0o755, parents=True, exist_ok=True)
        for key, values in dir_tree.items():
            lv1_dir = self.base_dir.joinpath(key)
            lv1_dir.mkdir(0o755, parents=True, exist_ok=True)
            for value in values:
                # 创建子目录
                lv2_dir = lv1_dir.joinpath(value)
                lv2_dir.mkdir(0o755, parents=True, exist_ok=True)

                # NOTE: 动态增加下载目录的属性，如: `dir_json_illust`
                setattr(self, f'dir_{key}_{value}', lv2_dir)

    def check_result(self, result):
        if 'error' in result:
            msg = result.error.message or result.error.user_message or ''
            if 'Rate Limit' in msg:
                # 访问太频繁被限制时
                raise NeedRetry('request rate limit')

            elif 'Please check your Access Token' in msg:
                # Access Token 失效，重新登录
                self.login()
                raise NeedRetry('access token expired, relogin')

            elif 'Offset must be no more than' in msg:
                logging.warning(msg)

            elif msg:
                logging.error(msg)

            else:
                logging.error(f'ApiError: {result.error}')  # 未知错误打印到日志

    def decorate_apis_with_retry(self):
        '''给api接口增加自动重试装饰器'''
        wrapper = ut.retry(checker=self.check_result, exceptions=(NeedRetry,))

        self.api.auth = wrapper(self.api.auth)
        self.api.illust_detail = wrapper(self.api.illust_detail)
        self.api.illust_ranking = wrapper(self.api.illust_ranking)
        self.api.illust_recommended = wrapper(self.api.illust_recommended)
        self.api.illust_related = wrapper(self.api.illust_related)
        self.api.login = wrapper(self.api.login)
        self.api.search_illust = wrapper(self.api.search_illust)
        self.api.user_bookmarks_illust = wrapper(self.api.user_bookmarks_illust)
        self.api.user_detail = wrapper(self.api.user_detail)
        self.api.user_illusts = wrapper(self.api.user_illusts)

    def login(self):
        '''登录 Pixiv 账号
            Return: {
                "access_token": "06ET0J9HpOVyZiX1tlrnIIrEVVe8Ubb-CGFGQtkkLwE",
                "expires_in": 3600,
                "refresh_token": "ajE8tYYbHPP1t8YPYVgW5vvAW8blm7KExI0wZ3TK0_w",
                "scope": "",
                "token_type": "bearer",
                "user": {
                    "account": "user_khgw7448",
                    "id": "62341582",
                    "is_mail_authorized": true,
                    "is_premium": false,
                    "mail_address": "lanhuermao@126.com",
                    "name": "FengPo",
                    "profile_image_urls": {
                        "px_16x16": "https://i.pximg.net/.../xxx.png",
                        "px_170x170": "https://i.pximg.net/.../xxx.png",
                        "px_50x50": "https://i.pximg.net/.../xxx.png"
                    },
                    "x_restrict": 1
                }
            }
        '''
        if self.refresh_token:
            logging.info('login by refresh_token')
            result = self.api.auth(refresh_token=self.refresh_token)
        else:
            logging.info('login by password')
            result = self.api.login(self.username, self.password)

        self.user = User(result['user'])

        logging.debug(f'access_token="{self.api.access_token}" '
                      f'refresh_token="{self.api.refresh_token}"')
        return result

    def fetch_illust(self, iid: int, keep_json=False):
        '''获取 illust 数据
            Return: {
                "caption": "ジャケット＋メイド服を考えた人は天才。",
                "create_date": "2020-09-22T10:13:06+09:00",
                "height": 1250,
                "id": 84533965,
                "image_urls": {
                    "square_medium": "https://i.pximg.net/.../84533965_p0_square1200.jpg"
                    "medium": "https://i.pximg.net/.../84533965_p0_master1200.jpg",
                    "large": "https://i.pximg.net/.../84533965_p0_master1200.jpg",
                },
                "is_bookmarked": false,
                "is_muted": false,

                // 仅多图时，此字段有值
                "meta_pages": [
                    {
                        "image_urls": {
                            "square_medium": "https://i.pximg.net/.../86571617_p0_square1200.jpg"
                            "medium": "https://i.pximg.net/.../86571617_p0_master1200.jpg",
                            "large": "https://i.pximg.net/.../86571617_p0_master1200.jpg",
                            "original": "https://i.pximg.net/.../86571617_p0.jpg",
                        }
                    },
                    ...
                ],

                // 仅单图时，此字段有值
                "meta_single_page": {
                    "original_image_url": "https://i.pximg.net/.../84533965_p0.jpg"
                },

                "page_count": 1,
                "restrict": 0,
                "sanity_level": 2,
                "series": null,
                "tags": [
                    {
                        "name": "女の子",
                        "translated_name": "girl"
                    },
                    ...
                ],
                "title": "さぼりメイド",
                "tools": [],
                "total_bookmarks": 5133,
                "total_comments": 13,
                "total_view": 25590,
                "type": "illust",
                "user": {
                    "account": "watoson117",
                    "id": 887024,
                    "is_followed": true,
                    "name": "Puracotte＊ぷらこ",
                    "profile_image_urls": {
                        "medium": "https://i.pximg.net/user-profile/img/2020/09/28/09/06/13/19428811_dcb45b4ba84836aaaf4afb8fab90a1ac_170.jpg"
                    }
                },
                "visible": true,
                "width": 1000,
                "x_restrict": 0
            }
        '''
        jsonfile: Path = self.dir_json_illust.joinpath(f'{iid}.json')  # type: ignore
        if jsonfile.exists():
            with jsonfile.open() as fp:
                illust = Illust(json.load(fp))
        else:
            result = self.api.illust_detail(iid)
            if 'illust' not in result:
                return
            illust = Illust(result['illust'])

            if keep_json and illust['visible']:
                ut.save_jsonfile(illust, filename=jsonfile.as_posix())

        return illust

    def ifetch(self, pixiv_api, keep_json=False):
        '''NOTE: 特别注意，此函数并非普通装饰器，需手动调用'''
        @wraps(pixiv_api)
        def api_caller(**kwargs):  # 仅接受 kwargs 形式的参数
            il = None
            while True:
                result = pixiv_api(**kwargs)
                if not result or not result.illusts:
                    break

                for il in result.illusts:
                    il = Illust(il)

                    if il.is_qualified(self.ifilter):
                        logging.debug(f'fetched Illust({il.id}) '
                                      f'created={il.create_date[:10]} '
                                      f'bookmark={il.total_bookmarks}')
                        if keep_json:
                            jsonfile = self.dir_json_illust.joinpath(f'{il.id}.json')
                            ut.save_jsonfile(il, jsonfile.as_posix())
                        yield il

                if result.next_url:
                    kwargs = self.api.parse_qs(next_url=result.next_url)  # 构造下一步参数
                    time.sleep(random.random() + random.randint(1, 3))
                    _kwargs = ut.params_to_str(kwargs=kwargs)
                    logging.debug(f'request next page: {pixiv_api.__name__}({_kwargs})')
                    continue
                else:
                    break

            # return the last one
            if il:
                return il
            else:
                _kwargs = ut.params_to_str(kwargs=kwargs)
                logging.warning(f'no illust found: {pixiv_api.__name__}({_kwargs})')
        return api_caller

    def download_illust(self, illust: dict, square=True, medium=False, large=False, origin=False):
        '''下载 illust 图片'''
        if illust['page_count'] == 1:
            urls = illust['image_urls']
            if square:
                self.api.download(urls['square_medium'], path=self.dir_img_square)  # type: ignore
            if medium:
                self.api.download(urls['medium'], path=self.dir_img_medium)  # type: ignore
            if large:
                self.api.download(urls['large'], path=self.dir_img_large)  # type: ignore
            if origin:
                url = illust["meta_single_page"]["original_image_url"]
                self.api.download(url, path=self.dir_img_origin)  # type: ignore
        else:
            for item in illust['meta_pages']:
                urls = item['image_urls']
                if square:
                    self.api.download(urls['square_medium'], path=self.dir_img_square)  # type: ignore
                if medium:
                    self.api.download(urls['medium'], path=self.dir_img_medium)  # type: ignore
                if large:
                    self.api.download(urls['large'], path=self.dir_img_large)  # type: ignore
                if origin:
                    self.api.download(urls["original"], path=self.dir_img_origin)  # type: ignore

    def multi_download(self, illusts: list, square=True, medium=False, large=False, origin=False):
        '''下载多个 illusts'''
        total = len(illusts)
        for num, illust in enumerate(illusts, start=1):
            self.download_illust(illust, square, medium, large, origin)
            logging.info(f'downloading progress: {num} / {total}')

    def fetch_artist(self, aid, keep_json=False):
        '''获取用户数据
            Return {
                "profile": {
                    "address_id": 13,
                    "background_image_url": "https://i.pximg.net/.../xxx.jpg",
                    "birth": "",
                    "birth_day": "07-20",
                    "birth_year": 0,
                    "country_code": "",
                    "gender": "female",
                    "is_premium": false,
                    "is_using_custom_profile_image": true,
                    "job": "技术关联",
                    "job_id": 3,
                    "pawoo_url": null,
                    "region": "日本 東京都",
                    "total_follow_users": 377,
                    "total_illust_bookmarks_public": 1509,
                    "total_illust_series": 0,
                    "total_illusts": 186,
                    "total_manga": 6,
                    "total_mypixiv_users": 47,
                    "total_novel_series": 0,
                    "total_novels": 0,
                    "twitter_account": "puracotte117",
                    "twitter_url": "https://twitter.com/puracotte117",
                    "webpage": null
                },
                "profile_publicity": {
                    "birth_day": "public",
                    "birth_year": "public",
                    "gender": "public",
                    "job": "public",
                    "pawoo": true,
                    "region": "public"
                },
                "user": {
                    "account": "watoson117",
                    "comment": "ぷらこと申します。\r\n時々イラストレーターをやっている会社員です。",
                    "id": 887024,
                    "is_followed": true,
                    "name": "Puracotte＊ぷらこ",
                    "profile_image_urls": {
                        "medium": "https://i.pximg.net/user-profile/.../xxx.jpg"
                    }
                },
                "workspace": {
                    "chair": "",
                    "comment": "",
                    "desk": "",
                    "desktop": "",
                    "monitor": "",
                    "mouse": "",
                    "music": "",
                    "pc": "",
                    "printer": "",
                    "scanner": "",
                    "tablet": "",
                    "tool": "",
                    "workspace_image_url": null
                }
            }
        '''
        jsonfile: Path = self.dir_json_user.joinpath(f'{aid}.json')
        if jsonfile.exists():
            with jsonfile.open() as fp:
                artist = JsonDict(json.load(fp))
        else:
            artist = self.api.user_detail(aid)
            if artist and 'user' in artist:
                if keep_json:
                    ut.save_jsonfile(artist, filename=jsonfile.as_posix())
            else:
                raise ValueError(f"can't download {aid}: {artist}")

        return artist

    def download_artist(self, aid, avatar=True):
        artist = self.fetch_artist(aid, True)
        if avatar:
            self.api.download(artist['user']['profile_image_urls']['medium'],
                              path=self.dir_img_avatar)

    def fetch_web_ranking(self, date: datetime.date, keep_json=False):
        '''从 Web 下载排行榜数据
            Return [
                {
                    "attr": "original",
                    "date": "2015年12月31日 00:09",
                    "height": 810,
                    "illust_book_style": "1",
                    "illust_content_type": {
                        "antisocial": false,
                        "bl": false,
                        "drug": false,
                        "furry": false,
                        "grotesque": false,
                        "homosexual": false,
                        "lo": false,
                        "original": true,
                        "religion": false,
                        "sexual": 0,
                        "thoughts": false,
                        "violent": false,
                        "yuri": false
                    },
                    "illust_id": 54339949,
                    "illust_page_count": "1",
                    "illust_series": false,
                    "illust_type": "0",
                    "illust_upload_timestamp": 1451489068,
                    "profile_img": "https://i.pximg.net/user-profile/img/2008/03/31/01/13/19/95581_886b0c6eadefd9d6df6a6776a015920d_50.jpg",
                    "rank": 1,
                    "rating_count": 1689,
                    "tags": [
                        "オリジナル",
                        "天使",
                        "空",
                        "透明感",
                        "ふつくしい",
                        "銀髪碧眼",
                        "女の子",
                        "銀髪",
                        "オリジナル50000users入り",
                        "横乳"
                    ],
                    "title": "70億人のゆめをみる",
                    "url": "https://i.pximg.net/c/240x480/img-master/img/2015/12/31/00/24/28/54339949_p0_master1200.jpg",
                    "user_id": 27517,
                    "user_name": "藤ちょこ（藤原）",
                    "view_count": 115439,
                    "width": 572,
                    "yes_rank": 2
                },
                ...
            ]
        '''
        jsonfile: Path = self.dir_json_ranking.joinpath(f'{date:%Y%m%d}.json')  # type: ignore
        if jsonfile.exists():
            with jsonfile.open() as fp:
                ranking = json.load(fp)
        else:
            ranking = []
            base_url = 'https://www.pixiv.net/ranking.php'
            url_tmpl = f'{base_url}?mode=daily&content=illust&date={date:%Y%m%d}&p=%s&format=json'
            headers = {'Referer': base_url}

            next_page = 1
            while next_page:
                url = url_tmpl % next_page
                resp = requests.get(url, headers=headers, stream=True)
                if resp.status_code != 200:
                    if 'error' in resp.text:
                        logging.error(resp.json()['error'])
                    else:
                        logging.error(resp.text)
                    break
                result = resp.json()
                ranking.extend(result['contents'])
                next_page = result.get('next')

            if keep_json:
                ut.save_jsonfile(ranking, jsonfile.as_posix())

        return ranking

    def ifetch_ranking(self, date, only_new=True, keep_json=True):
        web_ranking = self.fetch_web_ranking(date, keep_json)
        for il in web_ranking:
            # 检查是否只下载当天的数据
            if only_new and int(il['yes_rank']) != 0:
                continue

            # 获取 Illust 详细数据
            illust = self.fetch_illust(il['illust_id'], False)
            if illust and illust.is_qualified(self.ifilter):
                # 检查是否需要保存 json
                if keep_json:
                    jsonfile = self.dir_json_illust.joinpath(f'{illust.id}.json')
                    ut.save_jsonfile(illust, jsonfile.as_posix())

                logging.debug(f'fetched Illust({illust.id}) '
                              f'created={illust.create_date[:10]} '
                              f'bookmark={illust.total_bookmarks}')
                yield illust
            time.sleep(random.random() + random.randint(1, 3))

    def ifetch_artist_artwork(self, aid, keep_json=False):
        '''迭代获取 artist 的 Illust'''
        user_illusts_api = self.ifetch(self.api.user_illusts, keep_json)
        return user_illusts_api(user_id=aid)

    def ifetch_tag(self, word, start: Optional[str] = None, end: Optional[str] = None,
                   keep_json=False):
        '''迭代获取 Tag 的 Illust'''
        search_illust_api = self.ifetch(self.api.search_illust, keep_json)

        if self.user.is_premium:
            yield from search_illust_api(word=word, sort='popular_desc')
        elif start and end:
            while end > start:
                try:
                    yield from search_illust_api(word=word, sort='date_desc',
                                                 start_date=start, end_date=end)
                except StopIteration as e:
                    if e.value:
                        last_illust = e.value
                        last_date = datetime.datetime.fromisoformat(last_illust.create_date).date()
                        end = (last_date - datetime.timedelta(1)).isoformat()
                        logging.info(f'the illusts created before {end} have been checked')
                    else:
                        break
        else:
            raise ValueError('user is not premium, and both start and end are None')

    def ifetch_recommend(self, keep_json):
        '''迭代获取推荐的 Illust'''
        illust_recommended_api = self.ifetch(self.api.illust_recommended, keep_json)
        return illust_recommended_api()

    def ifetch_related(self, iid, keep_json):
        '''迭代获取某作品关联的 Illust'''
        illust_related_api = self.ifetch(self.api.illust_related, keep_json)
        return illust_related_api(illust_id=iid)
