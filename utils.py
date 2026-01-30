# utils.py
# ============================
# 工具函数：安全请求、文件判断、目录查找、meta.json、下载包装、旧目录迁移
# ============================

import os
import json
import time
import random
import shutil
import requests
from datetime import datetime
from typing import Optional
from config import (
    ROOT_DOWNLOAD_DIR,
    MISSING_LINKS_FILENAME,
    HEADERS,
    log_info,
    log_warning,
    log_error,
    RENAME_DRY_RUN
)


# ----------------------------
# 1. 文件存在且非空判断
# ----------------------------

def file_exists_and_nonempty(path: str) -> bool:
    """
    判断文件是否存在且大小 > 0 字节。
    """
    return os.path.isfile(path) and os.path.getsize(path) > 0


# ----------------------------
# 2. 安全请求（带重试 + 随机延迟）
# ----------------------------

def safe_request(session: requests.Session, url: str, max_retries: int = 30, delay_range=(2, 10)) -> Optional[requests.Response]:
    """
    安全请求函数：
    - 自动重试（默认 3 次）
    - 每次失败后随机延迟（默认 2-5 秒）
    - 记录日志，返回 None 表示最终失败
    - 使用全局 HEADERS，超时 20 秒
    """
    for attempt in range(1, max_retries + 1):
        try:
            log_info(f"[请求] 第 {attempt} 次：{url}")
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp
            log_warning(f"[请求] 状态码异常：{resp.status_code} → {url}")
        except Exception as e:
            log_error(f"[请求异常] {e} → {url}")

        # 未成功且还有重试次数：随机延迟后重试
        if attempt < max_retries:
            random_delay(delay_range)

    log_error(f"[失败] 多次重试仍失败：{url}")
    return None


# ----------------------------
# 3. 统计无效链接数量
# ----------------------------

def count_missing_links(save_dir: str) -> int:
    """
    统计“文件不存在的链接.txt”中的有效链接数量：
    - 文件名固定为 MISSING_LINKS_FILENAME；
    - 每一行一个链接；空行不计数。
    """
    path = os.path.join(save_dir, MISSING_LINKS_FILENAME)
    if not os.path.isfile(path):
        return 0

    count = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception as e:
        log_warning(f"[count_missing_links] 读取失败：{e} → {path}")
    return count


# ----------------------------
# 4. 统计已完成文件数量
# ----------------------------

def count_finished_files(save_dir: str) -> int:
    """
    统计目录下“已完成文件”的数量（改进版）：
    - 只统计“媒体/资源类”的已下载文件，不统计 meta.json、记录文件、临时文件等。
    - 排除项包括：
        * MISSING_LINKS_FILENAME（文件不存在的链接.txt）
        * meta.json（元数据文件）
        * 以 .part/.tmp/.partial 等常见临时后缀结尾的文件
        * 名称以 '.' 开头的隐藏文件（例如 .DS_Store）
    - 任何非空的普通文件且不在排除列表中都会被计为“已完成文件”。
    - 这样可以避免 meta.json 被误计入，导致作品被错误跳过。
    """
    if not os.path.isdir(save_dir):
        return 0

    # 明确排除的文件名（不计入已完成）
    excluded_names = {
        MISSING_LINKS_FILENAME,  # "文件不存在的链接.txt"
        "meta.json",             # 元数据文件，不计入媒体数量
        ".DS_Store",             # macOS 系统文件
    }

    # 明确排除的后缀（临时文件或非媒体）
    excluded_suffixes = (
        ".part",   # 常见下载临时后缀
        ".tmp",
        ".partial",
        ".download",
    )

    count = 0
    try:
        for name in os.listdir(save_dir):
            # 跳过排除的明确文件名
            if name in excluded_names:
                continue

            # 跳过隐藏文件（以 . 开头）
            if name.startswith("."):
                continue

            # 跳过临时后缀
            lower = name.lower()
            if any(lower.endswith(suf) for suf in excluded_suffixes):
                continue

            # 统计普通非空文件
            path = os.path.join(save_dir, name)
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                count += 1
    except Exception as e:
        log_warning(f"[count_finished_files] 统计失败：{e} → {save_dir}")
        return 0

    return count


# ----------------------------
# 5. 跨关键词查找作品目录（兼容旧格式）
# ----------------------------

def find_existing_work_dir(folder_name: str) -> Optional[str]:
    """
    在 download 根目录下查找同名作品目录。
    同时兼容旧格式目录：
    - 旧格式：date丨title丨total
    - 新格式：date丨title丨total丨hash
    匹配规则：
    - date 相同
    - title_truncated 相同（比较前 100 字符）
    - total 相同
    - hash 可有可无
    返回：找到的目录绝对路径或 None
    """
    if not os.path.isdir(ROOT_DOWNLOAD_DIR):
        return None

    # 解析目标 folder_name（支持新格式和无日期新格式）
    parts = folder_name.split("丨")
    # 目标可能为新格式（4 段）或无日期新格式（3 段）
    if len(parts) == 4:
        date_new, title_new, total_new, hash_new = parts
    elif len(parts) == 3:
        # 可能为无日期新格式：hash丨title丨total
        date_new = ""
        hash_new = parts[0]
        title_new = parts[1]
        total_new = parts[2]
    else:
        # 非标准格式，直接按精确匹配
        for sub in os.listdir(ROOT_DOWNLOAD_DIR):
            sub_path = os.path.join(ROOT_DOWNLOAD_DIR, sub)
            if not os.path.isdir(sub_path):
                continue
            candidate = os.path.join(sub_path, folder_name)
            if os.path.isdir(candidate):
                return candidate
        return None

    # 遍历所有子目录，查找匹配的新格式或旧格式目录
    for sub in os.listdir(ROOT_DOWNLOAD_DIR):
        sub_path = os.path.join(ROOT_DOWNLOAD_DIR, sub)
        if not os.path.isdir(sub_path):
            continue

        for folder in os.listdir(sub_path):
            fpath = os.path.join(sub_path, folder)
            if not os.path.isdir(fpath):
                continue

            parts_old = folder.split("丨")

            # 旧格式：date丨title丨total
            if len(parts_old) == 3:
                date_old, title_old, total_old = parts_old
                if date_old == date_new and title_old[:100] == title_new and total_old == total_new:
                    return fpath

            # 新格式：date丨title丨total丨hash 或 无日期新格式
            if len(parts_old) == 4:
                if folder == folder_name:
                    return fpath

            # 无日期新格式（hash丨title丨total）
            if len(parts_old) == 3:
                # 可能与无日期新格式冲突，已在旧格式判断中处理
                if parts_old[0] == hash_new and parts_old[1] == title_new and parts_old[2] == total_new:
                    return fpath

    return None


# ----------------------------
# 6. 写入 meta.json
# ----------------------------

def write_meta_json(
    save_dir: str,
    slug: str,
    hash8: str,
    title: str,
    title_truncated: str,
    date: str,
    total: int,
    file_type: str,
    thumb_url: str,
    list_source: str,
    source_url: str
):
    """
    写入 meta.json，包含你要求的所有字段：
    - slug, hash, title（完整）, title_truncated, date, total
    - file_type（image / video）, thumb_url, list_source, download_time, source
    """
    meta = {
        "slug": slug,
        "hash": hash8,
        "title": title,
        "title_truncated": title_truncated,
        "date": date,
        "total": total,
        "file_type": file_type,
        "thumb_url": thumb_url,
        "list_source": list_source,
        "download_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source_url
    }

    path = os.path.join(save_dir, "meta.json")
    try:
        os.makedirs(save_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)
        log_info(f"[meta.json] 已写入：{path}")
    except Exception as e:
        log_warning(f"[meta.json] 写入失败：{e} → {path}")


# ----------------------------
# 7. download_file 的包装（调用你已有的 mymodule.download_file）
# ----------------------------

def safe_download(url: str, filename: str, save_dir: str, headers=None):
    """
    download_file 的包装函数：
    - 你自己的 mymodule.download_file 会处理 404 并写入“文件不存在的链接.txt”
    - 这里做动态导入，避免循环依赖；未来可在此处加入重试/限速逻辑
    """
    try:
        from mymodule import download_file  # 动态导入
    except Exception as e:
        log_warning(f"[safe_download] 无法导入 mymodule.download_file：{e}")
        return

    try:
        download_file(url, filename, save_dir, headers=headers, max_retries=-1)
    except Exception as e:
        log_warning(f"[safe_download] 下载失败：{e} → {url}")


# ----------------------------
# 8. 旧目录匹配与重命名（迁移支持）
# ----------------------------

def match_old_format_dir(folder_name: str) -> Optional[str]:
    """
    在 ROOT_DOWNLOAD_DIR 下查找与 folder_name 对应的旧格式目录（date丨title丨total）。
    匹配规则：
      - 新格式 folder_name 解析为 date_new, title_new, total_new, hash_new
      - 遍历所有子目录下的文件夹，若某文件夹为旧格式（3 段），则比较：
          date_old == date_new
          title_old[:100] == title_new
          total_old == total_new
    返回匹配到的旧目录绝对路径或 None（不做任何移动）
    """
    if not os.path.isdir(ROOT_DOWNLOAD_DIR):
        return None

    parts = folder_name.split("丨")
    if len(parts) == 4:
        date_new, title_new, total_new, hash_new = parts
    elif len(parts) == 3:
        # 可能为无日期新格式（hash丨title丨total）
        date_new = ""
        hash_new = parts[0]
        title_new = parts[1]
        total_new = parts[2]
    else:
        return None

    for sub in os.listdir(ROOT_DOWNLOAD_DIR):
        sub_path = os.path.join(ROOT_DOWNLOAD_DIR, sub)
        if not os.path.isdir(sub_path):
            continue
        for folder in os.listdir(sub_path):
            fpath = os.path.join(sub_path, folder)
            if not os.path.isdir(fpath):
                continue
            parts_old = folder.split("丨")
            if len(parts_old) == 3:
                date_old, title_old, total_old = parts_old
                if date_old == date_new and title_old[:100] == title_new and total_old == total_new:
                    return fpath
    return None


def rename_old_dir_to_new(old_dir: str, new_parent_dir: str, new_folder_name: str, dry_run: bool = RENAME_DRY_RUN) -> Optional[str]:
    """
    将旧目录 old_dir 重命名（或移动）为 new_parent_dir/new_folder_name。
    - old_dir: 旧目录绝对路径
    - new_parent_dir: 新目录应放置的父目录（通常 BASE_DOWNLOAD_DIR）
    - new_folder_name: 新目录名（含 hash）
    - dry_run: True 时仅打印将要执行的操作，不实际移动
    返回：
    - 新目录绝对路径（如果成功或 dry_run），否则 None

    逻辑：
    1. 如果 new_parent_dir/new_folder_name 已存在，则不覆盖，返回该路径（认为已存在）
    2. 否则尝试 os.rename（原子操作），若跨文件系统失败则 fallback 到 shutil.move
    3. 在移动成功后，尝试更新 meta.json（如果存在），在 meta.json 中加入 hash 字段并写回
    4. 记录日志并返回新路径
    """
    if not os.path.isdir(old_dir):
        log_warning(f"[重命名] 旧目录不存在：{old_dir}")
        return None

    os.makedirs(new_parent_dir, exist_ok=True)
    new_dir = os.path.join(new_parent_dir, new_folder_name)

    # 如果目标目录已存在，直接返回目标路径（避免覆盖）
    if os.path.isdir(new_dir):
        log_info(f"[重命名] 目标目录已存在，跳过移动：{new_dir}")
        return new_dir

    log_info(f"[重命名] 将旧目录移动：{old_dir} -> {new_dir} (dry_run={dry_run})")

    if dry_run:
        # dry_run 模式下仅返回目标路径，不实际移动
        return new_dir

    try:
        # 尝试原子重命名（同一文件系统）
        os.rename(old_dir, new_dir)
    except OSError:
        # 可能跨文件系统，使用 shutil.move
        try:
            shutil.move(old_dir, new_dir)
        except Exception as e:
            log_warning(f"[重命名] 移动失败：{e}")
            return None

    # 如果目录内存在 meta.json，尝试更新 hash 字段（如果没有则添加）
    meta_path = os.path.join(new_dir, "meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}

        # 从 new_folder_name 提取 hash（最后一段）
        parts = new_folder_name.split("丨")
        hash8 = parts[-1] if len(parts) >= 4 else None
        if hash8:
            meta["hash"] = hash8
            # 如果没有 title_truncated，生成并写入
            if "title_truncated" not in meta and "title" in meta:
                meta["title_truncated"] = meta["title"][:100]
            # 更新 download_time 为当前时间（可选）
            meta["download_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=4)
                log_info(f"[meta.json] 已更新 hash：{meta_path}")
            except Exception as e:
                log_warning(f"[meta.json] 更新失败：{e} → {meta_path}")

    return new_dir

# ----------------------------
# 9. 随机延迟，模拟人类访问，降低被封风险
# ----------------------------

def random_delay(delay_range=(2, 10)):
    """随机延迟，模拟人类访问，降低被封风险"""
    delay = random.uniform(*delay_range)
    log_info(f"[延迟] 等待 {delay:.2f} 秒后重试…")
    time.sleep(delay)
