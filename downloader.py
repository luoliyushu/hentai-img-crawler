# downloader.py
# ============================
# 图片 / 视频下载逻辑
# ============================

import os
import subprocess
from typing import List, Dict
from config import (
    HEADERS,
    log_info,
    log_warning
)
from utils import (
    safe_download,
    file_exists_and_nonempty
)


# ----------------------------
# 1. 下载图片
# ----------------------------

def download_images(img_infos: List[Dict[str, str]], save_dir: str):
    """
    下载一篇作品的所有图片：
    - 文件名直接使用网页上的文件名；
    - 已存在且非空的文件会跳过；
    - safe_download 内部会处理 404，并在目录下写入“文件不存在的链接.txt”。
    """
    os.makedirs(save_dir, exist_ok=True)

    for info in img_infos:
        url = info["url"]
        filename = info["filename"]
        filepath = os.path.join(save_dir, filename)

        if file_exists_and_nonempty(filepath):
            log_info(f"[跳过图片] 已存在且非空：{filepath}")
            continue

        log_info(f"[下载图片] {filename} → {url}")
        safe_download(url, filename, save_dir, headers=HEADERS)


# ----------------------------
# 2. m3u8 → mp4 转换
# ----------------------------

def convert_m3u8_to_mp4(m3u8_path: str, mp4_path: str):
    """
    使用 ffmpeg 将本地 m3u8 转为 mp4。
    - 需要本地已安装 ffmpeg，并在 PATH 中可用。
    """
    log_info(f"[视频转换] m3u8 → mp4：{m3u8_path} → {mp4_path}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", m3u8_path,
        "-c", "copy",
        mp4_path
    ]

    try:
        subprocess.run(cmd, check=True)
        log_info(f"[视频转换] 完成：{mp4_path}")
    except Exception as e:
        log_warning(f"[视频转换失败] {e}")


# ----------------------------
# 3. 下载视频（mp4 或 m3u8）
# ----------------------------

def download_video(video_info: Dict[str, str], save_dir: str):
    """
    下载并处理视频：
    - mp4：直接下载
    - m3u8：先下载 m3u8，再转换为 mp4
    """
    os.makedirs(save_dir, exist_ok=True)

    url = video_info["url"]
    is_mp4 = video_info["is_mp4"]
    video_id = video_info["id"]
    mp4_name = video_info["mp4_name"]
    mp4_path = os.path.join(save_dir, mp4_name)

    # 如果 mp4 已存在且非空，则视为已完成
    if file_exists_and_nonempty(mp4_path):
        log_info(f"[跳过视频] mp4 已存在：{mp4_path}")
        return

    # mp4 情况
    if is_mp4:
        filename = mp4_name
        filepath = os.path.join(save_dir, filename)

        if file_exists_and_nonempty(filepath):
            log_info(f"[跳过视频源] 已存在：{filepath}")
        else:
            log_info(f"[下载视频(mp4)] {filename} → {url}")
            safe_download(url, filename, save_dir, headers=HEADERS)
        return

    # m3u8 情况
    m3u8_name = f"{video_id}.m3u8"
    m3u8_path = os.path.join(save_dir, m3u8_name)

    if not file_exists_and_nonempty(m3u8_path):
        log_info(f"[下载视频(m3u8)] {m3u8_name} → {url}")
        safe_download(url, m3u8_name, save_dir, headers=HEADERS)

    if file_exists_and_nonempty(m3u8_path):
        convert_m3u8_to_mp4(m3u8_path, mp4_path)
    else:
        log_warning(f"[视频转换失败] m3u8 文件不存在：{m3u8_path}")
