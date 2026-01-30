# main.py
# ============================
# 主流程 crawl()（已实现 CRAWL_MODE，并支持旧目录重命名迁移）
# - CRAWL_MODE = 1: 先收集所有列表项，再统一处理（默认）
# - CRAWL_MODE = 2: 每页解析后立即处理（边爬边下）
# ============================

import os
from typing import Optional, List, Dict
import requests

from config import (
    GLOBAL_PAGE,
    CRAWL_MODE,
    BASE_DOWNLOAD_DIR,
    LIST_MODE,
    log_info,
    log_warning,
    RENAME_DRY_RUN
)
from parser_list import (
    build_list_page_url,
    parse_last_page_and_total,
    parse_list_page,
    get_next_page_number
)
from parser_story import (
    parse_story_viewer,
    parse_detail_page_for_story_url,
    extract_slug
)
from config import make_folder_name
from utils import (
    find_existing_work_dir,
    match_old_format_dir,
    rename_old_dir_to_new,
    count_finished_files,
    count_missing_links,
    write_meta_json,
    safe_request,
    random_delay
)
from downloader import (
    download_images,
    download_video
)


# ----------------------------
# 处理单条作品（含旧目录迁移逻辑）
# ----------------------------
def process_item(session: requests.Session, item: dict, is_special_list: bool):
    """
    处理一条列表记录：
    - 解析详情页 Story Viewer 链接
    - 解析 Story Viewer（图片/视频）
    - 生成目录名（哈希方案）
    - 查找已有目录（新格式或旧格式）
      * 若找到新格式目录：复用并按跳过逻辑判断是否继续
      * 若找到旧格式目录且旧目录已完成：将旧目录重命名为新格式（可 dry-run），然后跳过
      * 若找到旧格式目录但未完成：复用旧目录继续下载，下载完成后再重命名为新格式
      * 若未找到任何目录：创建新目录并下载
    - 下载图片/视频
    - 写入 meta.json
    """
    detail_url = item.get("detail_url", "")
    title = item.get("title", "No Title")
    date = item.get("date", "")
    thumb_url = item.get("thumb_url", "")

    if not detail_url:
        log_warning("[详情] detail_url 为空，跳过该项")
        return

    log_info(f"[详情] {title}")

    # 1. 从详情页解析 Story Viewer 链接（使用 safe_request 内部）
    story_url = parse_detail_page_for_story_url(session, detail_url)
    if not story_url:
        log_warning(f"[详情] 未找到 Story Viewer，跳过：{detail_url}")
        return

    # 2. 解析 Story Viewer，获取图片 / 视频信息和总数
    img_infos, video_info, total = parse_story_viewer(session, story_url)

    # 3. 计算应有总数（兜底：图片数量 + 视频数量）
    expected_total = total if total > 0 else len(img_infos) + (1 if video_info else 0)
    if expected_total == 0:
        log_warning("[详情] total=0 且无图片无视频，跳过该作品")
        return

    # 4. 提取 slug
    slug = extract_slug(detail_url)

    # 5. 生成目录名（含 title 截断 + hash）
    folder_name, title_truncated, hash8 = make_folder_name(
        date=date,
        title=title,
        total=expected_total,
        slug=slug,
        is_special=(date == "")
    )

    # 6. 查找是否已有同名目录（跨关键词复用）
    existing_dir = find_existing_work_dir(folder_name)
    if existing_dir:
        # 找到新格式目录，直接复用
        save_dir = existing_dir
        log_info(f"[复用目录] 新格式目录已存在：{save_dir}")
        # 若已完成则跳过（下面会判断）
    else:
        # 未找到新格式目录，尝试匹配旧格式目录（date丨title丨total）
        old_dir = match_old_format_dir(folder_name)
        if old_dir:
            # 计算旧目录是否已完成（已完成文件数 + 无效链接数 >= expected_total）
            finished_files_old = count_finished_files(old_dir)
            missing_links_old = count_missing_links(old_dir)
            finished_total_old = finished_files_old + missing_links_old

            if finished_total_old >= expected_total:
                # 旧目录已完成：尝试重命名为新格式目录并跳过下载
                new_parent = BASE_DOWNLOAD_DIR
                new_folder_name = folder_name  # 新格式目录名（含 hash）
                # dry_run 使用全局配置 RENAME_DRY_RUN，生产运行可设为 False
                new_dir = rename_old_dir_to_new(old_dir, new_parent, new_folder_name, dry_run=RENAME_DRY_RUN)
                if new_dir:
                    save_dir = new_dir
                    log_info(f"[重命名并复用] {old_dir} -> {save_dir}")
                    log_info(f"[跳过作品] 旧目录已完成，跳过下载：{save_dir}")
                    return
                else:
                    # 如果重命名失败，仍然选择在新目录下继续处理（创建新目录）
                    log_warning(f"[重命名失败] 将在新目录下继续处理：{os.path.join(BASE_DOWNLOAD_DIR, new_folder_name)}")
                    save_dir = os.path.join(BASE_DOWNLOAD_DIR, new_folder_name)
            else:
                # 旧目录存在但未完成，选择复用旧目录继续下载
                save_dir = old_dir
                log_info(f"[复用旧目录继续下载] {save_dir}")
                # 在下载完成后会尝试把旧目录重命名为新格式（见后续逻辑）
        else:
            # 没有旧目录，按新目录创建
            save_dir = os.path.join(BASE_DOWNLOAD_DIR, folder_name)
            log_info(f"[新建目录] {save_dir}")

    # 7. 跳过逻辑：已完成文件数 + 无效链接数 >= 应有总数 → 跳过
    finished_files = count_finished_files(save_dir)
    missing_links = count_missing_links(save_dir)
    finished_total = finished_files + missing_links

    if finished_total >= expected_total:
        log_info(f"[跳过作品] 已完成 {finished_total}/{expected_total}：{save_dir}")
        # 如果 save_dir 是旧目录且尚未重命名为新格式（即目录名不包含 hash），尝试重命名
        # 这里判断：如果 save_dir 的目录名不包含 hash（即不是新格式），则尝试重命名
        base_name = os.path.basename(save_dir)
        if "丨" in base_name:
            parts = base_name.split("丨")
            # 新格式通常有 4 段（date丨title丨total丨hash）或无日期新格式（hash丨title丨total）
            if len(parts) == 3:
                # 旧格式，尝试重命名为新格式
                new_parent = BASE_DOWNLOAD_DIR
                new_folder_name = folder_name  # 新格式目录名（含 hash）
                new_dir = rename_old_dir_to_new(save_dir, new_parent, new_folder_name, dry_run=RENAME_DRY_RUN)
                if new_dir:
                    log_info(f"[完成后重命名] 旧目录已完成，已重命名为新目录：{new_dir}")
                else:
                    log_warning(f"[完成后重命名] 重命名失败：{save_dir} -> {os.path.join(new_parent, new_folder_name)}")
        return
    else:
        log_info(f"[继续作品] 已完成 {finished_total}/{expected_total}，继续下载：{save_dir}")

    # 8. 下载图片
    if img_infos:
        download_images(img_infos, save_dir)

    # 9. 下载视频
    if video_info:
        download_video(video_info, save_dir)

    # 10. 下载完成后再次检查是否为旧目录且已完成，如果是则重命名为新目录
    finished_files_after = count_finished_files(save_dir)
    missing_links_after = count_missing_links(save_dir)
    finished_total_after = finished_files_after + missing_links_after

    if finished_total_after >= expected_total:
        # 如果当前 save_dir 是旧格式目录（3 段），则尝试重命名为新格式
        base_name = os.path.basename(save_dir)
        parts = base_name.split("丨")
        if len(parts) == 3:
            # 旧格式，执行重命名
            new_parent = BASE_DOWNLOAD_DIR
            new_folder_name = folder_name  # 新格式目录名（含 hash）
            new_dir = rename_old_dir_to_new(save_dir, new_parent, new_folder_name, dry_run=RENAME_DRY_RUN)
            if new_dir:
                log_info(f"[下载完成后重命名] 已将旧目录重命名为新目录：{new_dir}")
                save_dir = new_dir
            else:
                log_warning(f"[下载完成后重命名] 重命名失败：{save_dir} -> {os.path.join(new_parent, new_folder_name)}")

    # 11. 写入 meta.json（无论是否重命名，meta.json 写入到最终 save_dir）
    file_type = "video" if video_info else "image"
    list_source = f"{LIST_MODE}"
    write_meta_json(
        save_dir=save_dir,
        slug=slug,
        hash8=hash8,
        title=title,
        title_truncated=title_truncated,
        date=date,
        total=expected_total,
        file_type=file_type,
        thumb_url=thumb_url,
        list_source=list_source,
        source_url=detail_url
    )


# ----------------------------
# 辅助：收集多页 items（用于 CRAWL_MODE = 1）
# ----------------------------
def collect_items_for_general_mode(session: requests.Session, start_page: int, last_page: int, first_page_html: Optional[str]) -> List[Dict]:
    """
    在“一般情况”下，如果 CRAWL_MODE == 1，先收集所有页面的 items 并返回列表。
    - start_page: 起始页（通常为 last_page 或 GLOBAL_PAGE）
    - last_page: 最后一页（解析得到）
    - first_page_html: 第 1 页的 HTML（如果已请求过可传入以避免重复请求）
    返回：按页面顺序（从旧到新）收集的 items 列表（便于后续统一处理）
    """
    items_all: List[Dict] = []

    # 从 start_page 往前到 1（包含）
    for page in range(start_page, 0, -1):
        log_info(f"[收集] 第 {page} 页（收集模式）")

        if page == 1 and first_page_html is not None and start_page == last_page:
            html = first_page_html
        else:
            resp = safe_request(session, build_list_page_url(page))
            if not resp:
                log_warning(f"[收集] 第 {page} 页获取失败，跳过该页")
                continue
            html = resp.text

        page_items = parse_list_page(html)
        # 保持页面内顺序（页面内从上到下），但我们希望最终按时间从旧到新处理，
        # 所以先把每页 items 反转（页面上新在上，反转后旧在前），然后 extend
        page_items = page_items[::-1]
        items_all.extend(page_items)

    log_info(f"[收集] 共收集到 {len(items_all)} 条 items")
    return items_all


# ----------------------------
# 主流程 crawl()
# ----------------------------
def crawl():
    """
    爬虫主流程（已实现 CRAWL_MODE）：
    - 先请求第一页，判断是“一般情况”还是“特殊情况”；
    - 一般情况：
        * CRAWL_MODE == 1：先收集所有 items（collect_items_for_general_mode），收集完成后统一处理；
        * CRAWL_MODE == 2：每页解析后立即处理（原有行为）。
    - 特殊情况：
        * CRAWL_MODE == 1：先从 GLOBAL_PAGE 或 last_page 开始，顺序收集所有页（向后），收集完成后统一处理；
        * CRAWL_MODE == 2：每页解析后立即处理（原有行为）。
    """
    session = requests.Session()

    # 请求第一页（使用 safe_request）
    first_resp = safe_request(session, build_list_page_url(1))
    if not first_resp:
        log_warning("[致命] 无法获取第一页")
        return

    last_page, total_count, is_special = parse_last_page_and_total(first_resp.text)

    # -------------------------
    # 特殊情况：通过 nextpostslink 一直往后爬
    # -------------------------
    if is_special:
        log_info("[特殊模式] 通过 nextpostslink 逐页爬取")

        # 起始页：GLOBAL_PAGE >0 则从该页开始，否则从 1 开始
        current_page = GLOBAL_PAGE if GLOBAL_PAGE > 0 else 1

        if CRAWL_MODE == 1:
            # 收集模式：先收集所有页的 items（向后遍历），再统一处理
            items_all: List[Dict] = []
            page = current_page
            while True:
                log_info(f"[收集-特殊] 第 {page} 页")
                resp = safe_request(session, build_list_page_url(page))
                if not resp:
                    log_warning(f"[收集-特殊] 第 {page} 页获取失败，停止收集")
                    break

                page_items = parse_list_page(resp.text)
                # 特殊模式下页面顺序通常是从新到旧，反转以便后续按旧→新处理
                page_items = page_items[::-1]
                items_all.extend(page_items)

                next_page = get_next_page_number(resp.text)
                if not next_page:
                    log_info("[收集-特殊] 已到最后一页")
                    break
                page = next_page

            log_info(f"[收集-特殊] 共收集到 {len(items_all)} 条，开始统一处理")
            for item in items_all:
                process_item(session, item, is_special_list=True)
                random_delay()

            return

        else:
            # CRAWL_MODE == 2：边爬边处理（原有行为）
            page = current_page
            while True:
                log_info(f"[列表] 第 {page} 页")

                resp = safe_request(session, build_list_page_url(page))
                if not resp:
                    log_warning(f"[列表] 第 {page} 页获取失败，停止该分支")
                    break

                items = parse_list_page(resp.text)
                items = items[::-1]  # 从下往上处理

                for item in items:
                    process_item(session, item, is_special_list=True)
                    random_delay()

                next_page = get_next_page_number(resp.text)
                if not next_page:
                    log_info("[列表] 已到最后一页")
                    break

                page = next_page

            return

    # -------------------------
    # 一般情况：从 last_page → 1
    # -------------------------
    start_page = GLOBAL_PAGE if GLOBAL_PAGE > 0 else last_page
    end_page = 1

    log_info(f"[一般模式] 从第 {start_page} 页 → 第 {end_page} 页")

    if CRAWL_MODE == 1:
        # 先收集所有 items（按页面顺序从旧到新），再统一处理
        items_all = collect_items_for_general_mode(session, start_page, last_page, first_resp.text)
        log_info(f"[处理] 开始统一处理 {len(items_all)} 条 items")
        for item in items_all:
            process_item(session, item, is_special_list=False)
            random_delay()
        return

    # CRAWL_MODE == 2：每页解析后立即处理（原有行为）
    for page in range(start_page, end_page - 1, -1):
        log_info(f"[列表] 第 {page} 页")

        if page == 1 and start_page == last_page:
            html = first_resp.text
        else:
            resp = safe_request(session, build_list_page_url(page))
            if not resp:
                log_warning(f"[列表] 第 {page} 页获取失败，跳过")
                continue
            html = resp.text

        items = parse_list_page(html)
        items = items[::-1]

        for item in items:
            process_item(session, item, is_special_list=False)
            random_delay()


# ----------------------------
# 入口
# ----------------------------
if __name__ == "__main__":
    crawl()
