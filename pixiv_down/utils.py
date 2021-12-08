import json
import logging
import time
from functools import wraps
from typing import Union

from pixivpy3.utils import JsonDict


def params_to_str(args=None, kwargs=None):
    '''将参数格式化为字符串'''
    s = ''
    if args:
        s += ', '.join(f'{a}' for a in sorted(args))
    if kwargs:
        if s:
            s += ', '
        s += ', '.join(f'{k}={v}' for k, v in sorted(kwargs.items()))
    return s


def singleton(cls):
    '''单例装饰器'''
    instance = None

    @wraps(cls)
    def deco(*args, **kwargs):
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance
    return deco


def retry(checker=None, exceptions=(Exception,)):
    '''
    @checker: 结果检查器，Callable 对象。接收被装饰函数的结果作为参数，返回 True 时进行重试
    @exceptions: 指定异常发生时，自动重试
    '''
    def deco(func):
        seconds = [5, 30, 60, 120, 300]

        @wraps(func)
        def wrapper(*args, **kwargs):
            for n in seconds:
                try:
                    result = func(*args, **kwargs)
                    if callable(checker):
                        checker(result)
                    return result
                except exceptions as e:
                    logging.error(f"retry after {n} sec due to `{e}`.")
                    time.sleep(n)
                    continue
            else:
                _arg = params_to_str(args, kwargs)
                logging.error(f'Retry Failed: {func.__name__}({_arg})')
        return wrapper
    return deco


def save_jsonfile(data, filename: str, compress=True):
    if not filename:
        raise ValueError('`filename` can not be null.')
    if not filename.endswith('.json'):
        filename = f'{filename}.json'
    with open(filename, 'w') as fp:
        if compress:
            json.dump(data, fp, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        else:
            json.dump(data, fp, ensure_ascii=False, sort_keys=True, indent=4)


def print_json(json_data: Union[str, bytes, dict], keys=()):
    '''打印 JSON 数据'''
    if isinstance(json_data, (str, bytes)):
        _data = JsonDict(json.loads(json_data))
    else:
        _data = JsonDict(json_data)

    if 'ALL' in keys:
        json_str = json.dumps(_data, sort_keys=True, indent=4, ensure_ascii=False)
        print(json_str)
    else:
        for k in keys:
            v = _data.get(k)
            if isinstance(v, (dict, list)):
                v = json.dumps(v, sort_keys=True, indent=4, ensure_ascii=False)
            print(f'{k} = {v}')
