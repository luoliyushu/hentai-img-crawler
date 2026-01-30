# parser_story.py
# ============================
# Story Viewer 解析（多图 / 单图 / 视频）+ slug 提取
# ============================

import re, requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Tuple, List, Dict, Optional
from config import (
    HEADERS,
    log_info,
    log_warning
)
from utils import safe_request


# ----------------------------
# 1. 提取 slug
# ----------------------------

def extract_slug(detail_url: str) -> str:
    """
    从详情页 URL 中提取 slug：
    例如：https://xxx/image/ai-photo-22-ai-generated-2/
    slug = ai-photo-22-ai-generated-2
    """
    parsed = urlparse(detail_url)
    parts = parsed.path.strip("/").split("/")
    return parts[-1] if parts else "unknown"


# ----------------------------
# 2. 从详情页解析 Story Viewer 链接
# ----------------------------

def parse_detail_page_for_story_url(session: requests.Session, detail_url: str) -> Optional[str]:
    """
    解析详情页，找到 “View in Story Viewer” 对应的链接。
    - 使用 safe_request 进行请求，失败返回 None。
    """
    resp = safe_request(session, detail_url)
    if not resp:
        log_warning(f"[详情页] 请求失败或超时：{detail_url}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    paginators = soup.find_all("div", id="paginator")
    story_url = None

    for p in paginators:
        a = p.find("a")
        if not a:
            continue
        text = a.get_text(strip=True).lower()
        if "view in story viewer" in text:
            story_url = a.get("href")
            break

    if not story_url:
        log_warning(f"[详情页] 未找到 Story Viewer 链接：{detail_url}")
        return None

    log_info(f"[详情页] Story Viewer：{story_url}")
    return story_url


# ----------------------------
# 3. 解析 Story Viewer 页面
# ----------------------------

def parse_story_viewer(session: requests.Session, story_url: str) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]], int]:
    """
    解析 Story Viewer 页面，支持多图 / 单图 / 视频。
    返回：
    - img_infos: 图片列表，每项 {"url":..., "filename":...}
    - video_info: 视频信息 dict 或 None
    - total: 标注的总数（图片总数或 1）
    """
    resp = safe_request(session, story_url)
    if not resp:
        log_warning(f"[Story Viewer] 请求失败或超时：{story_url}")
        return [], None, 0

    soup = BeautifulSoup(resp.text, "html.parser")

    # 保存 HTML 到本地，方便调试（可选）
    try:
        with open("output_story.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
    except Exception:
        pass

    img_infos: List[Dict[str, str]] = []
    video_info: Optional[Dict[str, str]] = None
    total = 0

    # -------------------------
    # 3.1 检查是否为视频（优先）
    # -------------------------
    cover_page = soup.find("amp-story-page", id="cover")
    if cover_page:
        amp_video = cover_page.find("amp-video")
        if amp_video:
            source = amp_video.find("source")
            if source and source.get("src"):
                video_url = source.get("src")
                is_mp4 = video_url.lower().endswith(".mp4")

                parts = urlparse(video_url).path.split("/")
                video_id = parts[-2] if len(parts) >= 2 else "video"
                mp4_name = f"{video_id}.mp4"

                video_info = {
                    "url": video_url,
                    "is_mp4": is_mp4,
                    "id": video_id,
                    "mp4_name": mp4_name
                }

                log_info(f"[Story Viewer] 检测到视频：{video_url}")
                return img_infos, video_info, 1

    # -------------------------
    # 3.2 多图 / 单图情况
    # -------------------------
    pages = soup.find_all(
        "amp-story-page",
        attrs={"id": lambda v: v != "custom-bookend-scrollable"}
    )

    for page in pages:
        img = page.find("amp-img")
        if not img:
            continue

        src = img.get("src")
        if not src:
            continue

        # 优先从 a.left 获取真实文件名
        a = page.select_one("amp-story-cta-layer a.left")
        if a and a.get("href"):
            href = a.get("href")
            filename = href.split("/")[-1]
            url_for_download = href
        else:
            filename = src.split("/")[-1]
            url_for_download = src

        img_infos.append({
            "url": url_for_download,
            "filename": filename
        })

    # -------------------------
    # 3.3 解析 total（SOURCE n/m）
    # -------------------------
    all_a = soup.select("amp-story-cta-layer a.left")
    if all_a:
        last_a = all_a[-1]
        text = last_a.get_text(strip=True)
        m = re.search(r"/(\d+)", text)
        if m:
            total = int(m.group(1))
        else:
            log_warning(f"[Story Viewer] 无法解析总数：{text}")

    # -------------------------
    # 3.4 total 兜底逻辑
    # -------------------------
    if total == 0:
        img_count = len(img_infos)
        if img_count == 1:
            total = 1
            log_info("[Story Viewer] 单图情况，总数设为 1")
        elif img_count > 1:
            total = img_count
            log_warning(f"[Story Viewer] 使用图片数量兜底 total={img_count}")
        else:
            total = 0
            log_warning("[Story Viewer] 未解析到任何图片")

    log_info(f"[Story Viewer] 解析到 {len(img_infos)} 张图片，总数 {total}")
    return img_infos, video_info, total
