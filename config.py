# config.py
# ============================
# 全局配置、日志系统、哈希函数、目录名生成（含对 date/title 的文件名合法化）
# 说明：
# - 优先使用你自己项目中的 mymodule.make_valid_filename（如果存在）。
# - 如果 mymodule 不可用，使用下面的回退实现：将常见的非法文件名字符替换为视觉上相似的全角或替代字符，
#   并把连续空白压缩为单个下划线，确保生成的目录名不会被误拆分为多级目录。
# - 这样可以避免像 "2013/04/15" 这种 date 导致目录被拆成多层的问题。
# ============================

import os
import hashlib
from datetime import datetime
import logging

# ----------------------------
# 1. 尝试导入你自己的 make_valid_filename（优先）
# ----------------------------
try:
    # 期望你在项目中有 mymodule.make_valid_filename，用于把任意字符串变成合法文件名
    from mymodule import make_valid_filename  # type: ignore
except Exception:
    # 回退实现：用视觉相近的字符替换常见非法字符，避免路径分隔和保留可读性
    def make_valid_filename(s: str) -> str:
        """
        回退实现：将常见的非法文件名字符替换为相似字符，保证不会包含路径分隔符或系统保留字符。
        替换表（示例）：
            '\\' -> '⧵'
            '/'  -> '／'
            ':'  -> '：'
            '*'  -> '＊'
            '?'  -> '？'
            '"'  -> '＂'
            '<'  -> '＜'
            '>'  -> '＞'
            '|'  -> '｜'
        其他处理：
        - 将连续空白压缩为单个下划线
        - 去除首尾空白
        - 保证返回字符串非空（若输入为空或 None，返回空字符串）
        """
        if s is None:
            return ""
        s = str(s).strip()

        # 替换映射：把可能导致路径拆分或非法的字符替换为视觉相近的全角或替代字符
        replace_map = {
            "\\": "⧵",
            "/": "／",
            ":": "：",
            "*": "＊",
            "?": "？",
            "\"": "＂",
            "<": "＜",
            ">": "＞",
            "|": "｜"
        }

        # 先逐字符替换
        out_chars = []
        for ch in s:
            if ch in replace_map:
                out_chars.append(replace_map[ch])
            else:
                out_chars.append(ch)
        s = "".join(out_chars)

        # 将控制字符和不可见字符移除（保守处理）
        s = "".join(ch for ch in s if ch.isprintable())

        # 把连续空白（空格、制表符等）压缩为单个下划线，避免文件名中出现多空格
        parts = s.split()
        s = "_".join(parts)

        # 最后再做一次保底替换：如果结果为空，返回一个下划线占位
        if not s:
            return "_"

        return s


# ----------------------------
# 2. 日志系统初始化
# ----------------------------
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
# 3. 全局配置
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
RENAME_DRY_RUN = False


# ----------------------------
# 4. 哈希函数（slug → 8 位 hash）
# ----------------------------
def slug_to_hash(slug: str) -> str:
    """
    将 slug 转为 md5 的前 8 位，用于目录名。
    - slug 一般为详情页 URL 的最后一段，例如：
      /image/ai-photo-22-ai-generated-2/ → ai-photo-22-ai-generated-2
    """
    h = hashlib.md5(str(slug).encode("utf-8")).hexdigest()
    return h[:8]


# ----------------------------
# 5. 目录名生成（含 title 截断 + 文件名合法化）
# ----------------------------
def make_folder_name(date: str, title: str, total: int, slug: str, is_special: bool):
    """
    生成作品目录名（哈希方案），并对 date/title 做合法化处理以避免路径注入：
    - 一般情况（有日期）：
        {date_clean}丨{title_truncated_clean}丨{total}丨{hash}
    - 特殊情况（无日期）：
        {hash}丨{title_truncated_clean}丨{total}

    处理细节：
    - title_truncated: 先截断到 100 字符，再调用 make_valid_filename 清洗非法字符
    - date: 先调用 make_valid_filename 清洗（把 '/' 或 '\' 等替换掉），
            如果 date 本身包含多级路径（例如 "2013/04/15"），清洗后会变成单一字符串（例如 "2013_04_15"）
    - hash8: slug 的 md5 前 8 位

    返回：
    - folder: 最终目录名（单层，不含路径分隔符）
    - title_truncated_clean: 清洗后的截断标题
    - hash8: 8 位哈希
    """
    # 保护性转换，避免 None 导致异常
    title = "" if title is None else str(title)
    date = "" if date is None else str(date)
    slug = "" if slug is None else str(slug)

    # 截断标题（目录名用），避免路径过长
    title_truncated = title[:100]

    # 使用 make_valid_filename 清洗 title 和 date（优先使用 mymodule 的实现）
    title_truncated_clean = make_valid_filename(title_truncated)
    date_clean = make_valid_filename(date)

    # 生成哈希
    hash8 = slug_to_hash(slug)

    if is_special:
        # 无日期情况：hash 开头
        folder = f"{hash8}丨{title_truncated_clean}丨{total}"
    else:
        # 有日期情况：使用清洗后的 date_clean（保证单层目录）
        folder = f"{date_clean}丨{title_truncated_clean}丨{total}丨{hash8}"

    return folder, title_truncated_clean, hash8
