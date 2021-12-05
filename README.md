# Pixiv Downloader

## Install

```shell
pip install pixiv-dl
```

## Usage

```shell
pixiv-dl [OPTIONS] download_type [other_args ...]
```

### Download Types

- iid
- aid
- tag
- rcmd
- related

### Other Args

the follow args for download type, exp. e.g., `tag name` or `illust id list`.

### Optional Arguments:

* `-h, --help`
    show help message and exit

* `-b MIN_BOOKMARKS`
    default is 3000
    the min bookmarks of illust. ()

* `-c MAX_IMG_COUNT`
    default is 10
    the max img count of one illust. ()

* `-t TOTAL_CRAWLS` or `-n TOTAL_CRAWLS`
    default is 100
    the total illusts of crawls. ()

* `-p PATH`
    default is `./`
    the storage path ()

* `-d DOWNLOAD`
    download types: s/m/l/o. means that: square/middle/large/origin. can set multiple.

* `-k`
    keep json files

* `-s START`
    default is `2021-12-05`
    the start date of illust with a tag. only used for tag. ()

* `-e END`
    default is `2016-01-01`
    the end date of illust with a tag. only used for tag. ()

* `-l {debug,info,warn,error}`
    default is `warn`
    the log level ()
