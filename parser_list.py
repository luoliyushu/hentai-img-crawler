# parser_list.py
# ============================
# 列表页解析（一般情况 + 特殊情况）
# ============================

import re
from bs4 import BeautifulSoup
from config import (
    DOMAIN,
    LIST_MODE,
    SEARCH_KEYWORD,
    SEARCH_TAG,
    log_info,
    log_warning
)


# ----------------------------
# 1. 构造列表页 URL
# ----------------------------

def build_list_page_url(page: int) -> str:
    """
    根据 LIST_MODE 构造列表页 URL。
    规则：
    - 第 1 页不带 /page/1/
    - 第 n 页带 /page/n/
    """
    if LIST_MODE == "search_keyword":
        base = f"/search/keyword/{SEARCH_KEYWORD}/"
    elif LIST_MODE == "search_tag":
        base = f"/search/tag/{SEARCH_TAG}/"
    elif LIST_MODE == "ranking":
        base = "/ranking/"
    elif LIST_MODE == "ranking_video":
        base = "/ranking-video/"
    elif LIST_MODE == "ranking_download":
        base = "/ranking-download/"
    elif LIST_MODE == "ranking_bookmark":
        base = "/ranking-bookmark/"
    elif LIST_MODE == "ranking_like":
        base = "/ranking-like/"
    elif LIST_MODE == "search_video":
        base = "/search-video/"
    else:
        base = f"/search/keyword/{SEARCH_KEYWORD}/"

    if page <= 1:
        return f"https://{DOMAIN}{base}"
    else:
        return f"https://{DOMAIN}{base}page/{page}/"


# ----------------------------
# 2. 判断是否为“特殊情况”
# ----------------------------

def parse_last_page_and_total(html: str):
    """
    从第一页 HTML 中解析：
    - last_page: 最后一页页码（一般情况）
    - total_count: 搜索结果总数（一般情况）
    - is_special: 是否为“特殊情况”（无总数、无 last 链接）
    """
    soup = BeautifulSoup(html, "html.parser")

    # 搜索结果总数
    total = 0
    span = soup.select_one("#articles_number .immoral_all_items")
    if span and span.text.strip().isdigit():
        total = int(span.text.strip())

    # 最后一页
    last_page = None
    last_link = soup.select_one(".wp-pagenavi a.last")
    if last_link:
        m = re.search(r"/page/(\d+)/", last_link.get("href", ""))
        if m:
            last_page = int(m.group(1))

    # 特殊情况：无总数 或 无 last 链接
    is_special = not (total > 0 and last_page is not None)

    if is_special:
        log_info("[列表解析] 检测到『特殊情况』：无总数或无最后一页")
        return None, 0, True

    log_info(f"[列表解析] 一般情况：总数 {total}，最后一页 {last_page}")
    return last_page, total, False


# ----------------------------
# 3. 解析列表页
# ----------------------------

def parse_list_page(html: str):
    """
    解析列表页，返回一个 item 列表：
    每个 item 包含：
    - detail_url：详情页 URL
    - thumb_url：缩略图 URL（可能为空）
    - title：标题
    - date：日期（可能为空）
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    ul = soup.find("ul", id="image-list")
    if not ul:
        log_warning("[列表解析] 未找到 ul#image-list")
        return results

    for li in ul.find_all("li"):
        item = {}

        # 图片 + 详情页链接
        a = li.select_one(".image-list-item-image a")
        if a:
            href = a.get("href", "")
            item["detail_url"] = f"https://{DOMAIN}{href}"

            img = a.find("img")
            if img:
                item["thumb_url"] = img.get("src", "")
            else:
                item["thumb_url"] = ""
        else:
            item["detail_url"] = ""
            item["thumb_url"] = ""

        # 标题
        title_a = li.select_one(".image-list-item-title a")
        if title_a:
            item["title"] = " ".join(title_a.get_text(strip=True).split())
        else:
            item["title"] = "No Title"

        # 日期（特殊情况可能为空）
        date_span = li.select_one(".image-list-item-regist-date span")
        if date_span and date_span.get_text(strip=True):
            item["date"] = date_span.get_text(strip=True)
        else:
            item["date"] = ""

        results.append(item)

    log_info(f"[列表解析] 本页解析到 {len(results)} 条")
    return results


# ----------------------------
# 4. 特殊情况：解析下一页页码
# ----------------------------

def get_next_page_number(html: str):
    """
    特殊情况：从 nextpostslink 中解析下一页页码。
    - 仅在“特殊模式”下使用。
    """
    soup = BeautifulSoup(html, "html.parser")
    a_next = soup.select_one(".wp-pagenavi a.nextpostslink")
    if not a_next:
        return None

    href = a_next.get("href", "")
    m = re.search(r"/page/(\d+)/", href)
    if m:
        return int(m.group(1))

    return None
