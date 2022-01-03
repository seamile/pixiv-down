# Pixiv Downloader

A command line pixiv illust downloader.


## Install

```shell
pip install pixiv-down
```


## Usage

```shell
usage: pixd [-h]
            [-b MIN_BOOKMARKS] [-c MAX_PAGE_COUNT] [-n ILLUST_NUM]
            [-k] [-p PATH] [-r RESOLUTION]
            [-s START] [-e END]
            [-l {debug,info,warn,error}]
            {iid,aid,tag,rcmd,related,ranking} ...
```


### Download illusts in diffrent ways

- `iid`

    download illusts by illust id list.

    e.g., `pixd iid 92578547 93005923 87052390 91681788`

- `aid`

    download illusts by artist id list.

    e.g., `pixd aid 671593 8062849 10475690 14496985`

- `tag`

    download illusts by tag name.

    e.g., `pixd tag 甘雨 刻晴 八重樱`

- `rcmd`

    download illusts from recomments.

    e.g., `pixd rcmd`

- `related`

    download related illusts of the specified illust id.

    e.g., `pixd related 70937229 87749466`

- `ranking`

    download daily ranking of the specified day.

    e.g., `pixd ranking 2021-01-01 2021-02-01,2021-03-31`

### Optional Arguments

- `-h, --help`

    show this help message and exit

- `-b MIN_BOOKMARKS`

    the min bookmarks of illust (default: 3000)

- `-c MAX_PAGE_COUNT`

    the max page count of illust (default: 10)

- `-q MIN_QUALITY`

    the min quality of illust, the quality eauals the num of bookmarks
    per 100 views (default: None)

- `-l {1,2,3}`

    the max sex level of illust (default: 2)

- `-n ILLUST_NUM`

    total number of illusts to download (default: 300)

- `-p PATH`

    the storage path of illusts (default: ./)

- `-r RESOLUTION`

    the resolution of illusts: `s` / `m` / `l` / `o`,

    i.e., square / middle / large / origin, can set multiple

- `-k`

    keep the json result to files

- `--show SHOW_JSON`

    print the json result on stdout

- `-s START`

    the start date of illust for tag searching (default: `2016-01-01`)

- `-e END`

    the end date of illust for tag searching (default: today)

- `--only_new`

    only download the newest illusts from ranking

- `--without_illust`

    don't download illusts when download ranking

- `-l {debug,info,warn,error}`

    the log level (default: `warn`)
