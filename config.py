# config.py
# ============================
# 全局配置、日志系统、哈希函数、目录名生成
# ============================

import os
import hashlib
from datetime import datetime
import logging

# ----------------------------
# 1. 日志系统初始化
# ----------------------------

# 日志目录：logs（不存在则创建）
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件名：crawler_YYYYMMDD_HHMMSS.log
log_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"crawler_{log_ts}.log")

# logging 基本配置（写文件并保留控制台打印）
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

def log_info(msg: str):
    """普通信息日志 + 同步打印到控制台"""
    print(msg)
    logging.info(msg)

def log_warning(msg: str):
    """警告信息日志 + 同步打印到控制台"""
    print(msg)
    logging.warning(msg)

def log_error(msg: str):
    """错误信息日志 + 同步打印到控制台"""
    print(msg)
    logging.error(msg)


# ----------------------------
# 2. 全局配置
# ----------------------------

# 站点域名（根据目标站点修改）
DOMAIN = "hentai-img.com"

# 列表模式（运行前修改）
# 可选值：
#   "search_keyword", "search_tag", "ranking", "ranking_video",
#   "ranking_download", "ranking_bookmark", "ranking_like", "search_video"
LIST_MODE = "search_keyword"

# 关键词 / 标签（仅在对应模式下生效）
SEARCH_KEYWORD = "stripping"
SEARCH_TAG = "anal"

# 下载根目录：[当前目录]/download
ROOT_DOWNLOAD_DIR = os.path.join(os.getcwd(), "download")
os.makedirs(ROOT_DOWNLOAD_DIR, exist_ok=True)

# 当前模式对应的子目录名（用于区分不同来源）
if LIST_MODE == "search_keyword":
    DOWNLOAD_SUBDIR_NAME = f"kw_{SEARCH_KEYWORD}"
elif LIST_MODE == "search_tag":
    DOWNLOAD_SUBDIR_NAME = f"tag_{SEARCH_TAG}"
else:
    DOWNLOAD_SUBDIR_NAME = LIST_MODE

# 当前模式下载目录：[当前目录]/download/{DOWNLOAD_SUBDIR_NAME}
BASE_DOWNLOAD_DIR = os.path.join(ROOT_DOWNLOAD_DIR, DOWNLOAD_SUBDIR_NAME)
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

# 页码控制说明：
# - 一般情况：GLOBAL_PAGE > 0 表示从该页往前爬到第 1 页；=0 表示从最后一页开始往前爬
# - 特殊情况：GLOBAL_PAGE > 0 表示从该页开始往后爬到没有下一页为止；=0 表示从第 1 页开始往后爬
GLOBAL_PAGE = 0

# 爬取模式：1=先收集所有列表再统一处理；2=每页获取后立刻处理
CRAWL_MODE = 2

# HTTP 请求头（可根据需要扩展）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "cookie": "mdlct=955dab4f278c2458c9eccfa45b3bb804; cf_clearance=kUunASv5buBIClduwZEEUzG0JZXYrZ4HM.EGkMlpiHA-1769609295-1.2.1.1-jmp5ZqUOQM2MT71sdGh2L7vzGBb0eibksiIHMzs1YPubN117j9zC_tCGqxHidZ_UmW2aqupAREhtjW.nOGVPI6az9rQamQG.y3jpOmycE.kPXG2diqBVprEzSHs7u8bYKeiREcTDNjSQFDRkDUXKRc_zc7Fh8g_McLTHmSCiMnI3oXvfB05iUg68OJbQDzv.IRovI13qZNnbALNsEfu4ULzZ3PMfmLfjbzIuP.vv05g"
}

# “文件不存在的链接”记录文件名
MISSING_LINKS_FILENAME = "文件不存在的链接.txt"

# 当检测到旧目录并准备重命名时，是否仅做 dry-run（True 仅打印不实际移动）
# 生产运行时可设为 False 执行实际重命名
RENAME_DRY_RUN = False


# ----------------------------
# 3. 哈希函数（slug → 8 位 hash）
# ----------------------------

def slug_to_hash(slug: str) -> str:
    """
    将 slug 转为 md5 的前 8 位，用于目录名。
    - slug 一般为详情页 URL 的最后一段，例如：
      /image/ai-photo-22-ai-generated-2/ → ai-photo-22-ai-generated-2
    """
    h = hashlib.md5(slug.encode("utf-8")).hexdigest()
    return h[:8]


# ----------------------------
# 4. 目录名生成（含 title 截断）
# ----------------------------

def make_folder_name(date: str, title: str, total: int, slug: str, is_special: bool):
    """
    生成作品目录名（哈希方案）：
    - 一般情况（有日期）：
        {date}丨{title_truncated}丨{total}丨{hash}
    - 特殊情况（无日期）：
        {hash}丨{title_truncated}丨{total}

    返回：
    - folder: 目录名（字符串）
    - title_truncated: 截断后的标题（前 100 字符）
    - hash8: slug 的 md5 前 8 位
    """
    # 截断标题（目录名用），避免路径过长
    title_truncated = title[:100]

    # 生成哈希
    hash8 = slug_to_hash(slug)

    if is_special:
        # 无日期情况：用 hash 开头
        folder = f"{hash8}丨{title_truncated}丨{total}"
    else:
        # 有日期情况：用 date 开头
        folder = f"{date}丨{title_truncated}丨{total}丨{hash8}"

    return folder, title_truncated, hash8
