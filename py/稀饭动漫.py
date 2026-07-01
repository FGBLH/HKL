# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。
# junyouyun

import re
import json
from urllib.parse import quote, urljoin, parse_qs
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

BASE = "https://anime.xifanacg.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": BASE,
}

CLASS_OPTIONS = {
    "1": ["搞笑", "原创", "轻小说改", "恋爱", "百合", "漫改", "校园", "战斗", "治愈", "奇幻",
          "日常", "青春", "乙女向", "悬疑", "后宫", "科幻", "冒险", "热血", "异世界", "游戏改",
          "音乐", "偶像", "美食", "耽美"],
    "2": ["搞笑", "原创", "轻小说改", "恋爱", "百合", "漫改", "校园", "战斗", "治愈", "奇幻",
          "日常", "青春", "乙女向", "悬疑", "后宫", "科幻", "冒险", "热血", "异世界", "游戏改",
          "音乐", "偶像", "美食", "耽美", "2026年1月", "2025年10月"],
    "3": [],
    "21": [],
}

AREA_OPTIONS = {
    "1": ["日本"],
    "2": [],
    "3": ["日本"],
    "21": [],
}

YEAR_RANGE = [str(y) for y in range(2026, 2004, -1)]

ORDER_OPTIONS = [
    {"n": "按最新", "v": "time"},
    {"n": "按最热", "v": "hits"},
    {"n": "按评分", "v": "score"},
]


class Spider(Spider):
    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get_decoded_html(self, url):
        r = self.session.get(url, timeout=15)
        r.encoding = r.apparent_encoding if r.apparent_encoding else 'utf-8'
        return r.text

    def _parse_vod_cards(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        for box in soup.select('.public-list-box.public-pic-b'):
            link = box.select_one('a.public-list-exp')
            if not link:
                continue
            href = link.get('href', '')
            vid = href.split('/')[-1].replace('.html', '')
            title = link.get('title', '')
            img = box.select_one('img.gen-movie-img')
            pic = img.get('data-src', '') if img else ''
            prb = box.select_one('.public-list-prb')
            remarks = prb.get_text(strip=True) if prb else ''
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })
        return vod_list

    def homeContent(self, filter):
        classes = [
            {"type_name": "连载新番", "type_id": "1"},
            {"type_name": "完结旧番", "type_id": "2"},
            {"type_name": "剧场版", "type_id": "3"},
            {"type_name": "美漫", "type_id": "21"},
        ]
        filters = {}
        for tid in ["1", "2", "3", "21"]:
            f_list = []
            if CLASS_OPTIONS[tid]:
                f_list.append({
                    "key": "class", "name": "类型",
                    "value": [{"n": "全部", "v": ""}] + [{"n": c, "v": c} for c in CLASS_OPTIONS[tid]]
                })
            if AREA_OPTIONS[tid]:
                f_list.append({
                    "key": "area", "name": "地区",
                    "value": [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in AREA_OPTIONS[tid]]
                })
            if tid != "21":
                f_list.append({
                    "key": "year", "name": "年份",
                    "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in YEAR_RANGE]
                })
            f_list.append({"key": "by", "name": "排序", "value": ORDER_OPTIONS})
            filters[tid] = f_list
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        try:
            html = self._get_decoded_html(BASE)
            return {"list": self._parse_vod_cards(html)}
        except Exception:
            data = self.categoryContent("1", "1", False, {})
            return {"list": data.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类列表：POST 请求 /index.php/ds_api/vod
        传递完整表单参数（包含空字段 lang/version/state/letter/time/level/weekday）
        """
        # 2. 构建完整表单数据（必须包含所有字段，空值用空字符串）
        form_data = {
            'type': tid,
            'class': extend.get("class", ""),
            'area': extend.get("area", ""),
            'year': extend.get("year", ""),
            'lang': extend.get("lang", ""),
            'version': extend.get("version", ""),
            'state': extend.get("state", ""),
            'letter': extend.get("letter", ""),
            'time': extend.get("time", ""),
            'level': extend.get("level", "0"),
            'weekday': extend.get("weekday", ""),
            'by': extend.get("by", "time"),
            'page': pg,
        }
        url = f"{BASE}/index.php/ds_api/vod"
        try:
            r = self.session.post(url, data=form_data, timeout=15)
            data = r.json()
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 40, "total": 0}

        vod_list = []
        for item in data.get("list", []):
            vod_id = str(item.get("vod_id", ""))
            actor_raw = item.get("vod_actor", "")
            actor = ','.join([a for a in actor_raw.split(',') if a.strip()]) if actor_raw else ''
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": item.get("vod_name", ""),
                "vod_pic": item.get("vod_pic", ""),
                "vod_remarks": item.get("vod_remarks", ""),
                "vod_actor": actor,
                "vod_douban_score": str(item.get("vod_douban_score", "")) if item.get("vod_douban_score") else "",
            })
        return {
            "list": vod_list,
            "page": int(data.get("page", pg)),
            "pagecount": int(data.get("pagecount", 1)),
            "limit": int(data.get("limit", 40)),
            "total": int(data.get("total", 0)),
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        url = f"{BASE}/bangumi/{vid}.html"
        try:
            html = self._get_decoded_html(url)
        except Exception:
            return {"list": [{"vod_id": vid, "vod_name": "获取失败"}]}

        soup = BeautifulSoup(html, 'html.parser')
        name = soup.select_one('h3.slide-info-title')
        name = name.text.strip() if name else ''
        pic_tag = soup.select_one('.detail-pic img.lazy')
        pic = pic_tag.get('data-src', '') if pic_tag else ''
        score_tag = soup.select_one('.fraction')
        score = score_tag.text.strip() if score_tag else ''
        remarks_tag = soup.select_one('.slide-info-remarks')
        remarks = remarks_tag.text.strip() if remarks_tag else ''

        director = actor = area = year = desc = ''
        param_box = soup.select_one('.info-parameter')
        if param_box:
            for li in param_box.find_all('li'):
                em = li.find('em')
                if not em:
                    continue
                key = em.get_text(strip=True).rstrip('：').rstrip(':')
                li_clone = BeautifulSoup(str(li), 'html.parser')
                for e in li_clone.find_all('em'):
                    e.decompose()
                value = li_clone.get_text(strip=True)
                if '导演' in key:
                    director = value
                elif '主演' in key:
                    actor = value
                elif '地区' in key:
                    area = value
                elif '年份' in key:
                    year = value
                elif '简介' in key:
                    desc = value

        if not director:
            d_tag = soup.find('strong', string=re.compile('导演'))
            if d_tag and d_tag.find_next('a'):
                director = d_tag.find_next('a').text.strip()
        if not actor:
            a_tag = soup.find('strong', string=re.compile('演员'))
            if a_tag:
                actor_links = a_tag.find_next_siblings('a')
                actor = ','.join([a.text.strip() for a in actor_links]) if actor_links else ''
        if not desc:
            desc_div = soup.select_one('#height_limit')
            desc = desc_div.text.strip() if desc_div else ''

        play_from, play_url = [], []
        tab_links = soup.select('.anthology-tab .swiper-slide')
        list_boxes = soup.select('.anthology-list-box')
        for idx, box in enumerate(list_boxes):
            line_name = f"线路{idx+1}"
            if idx < len(tab_links):
                raw = tab_links[idx].get_text(strip=True)
                badge = tab_links[idx].find('span', class_='badge')
                if badge:
                    raw = raw.replace(badge.text, '').strip()
                if raw:
                    line_name = raw
            play_from.append(line_name)
            eps = [f"{a.text.strip()}${urljoin(BASE, a['href'])}" for a in box.select('li a.this-link')]
            play_url.append("#".join(eps))

        vod = {
            "vod_id": str(vid), "vod_name": name, "vod_pic": pic,
            "vod_score": score, "vod_remarks": remarks,
            "vod_year": year, "vod_area": area, "vod_actor": actor,
            "vod_director": director, "vod_content": desc,
            "vod_play_from": "$$$".join(play_from) if play_from else "",
            "vod_play_url": "$$$".join(play_url) if play_url else "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        # 优先使用 AJAX suggest 接口
        try:
            url = f"{BASE}/index.php/ajax/suggest?mid=1&wd={quote(key)}"
            r = self.session.get(url, timeout=10)
            data = r.json()
            vod_list = []
            for item in data.get("list", []):
                vod_list.append({
                    "vod_id": str(item.get("id", "")),
                    "vod_name": item.get("name", ""),
                    "vod_pic": item.get("pic", ""),
                })
            if vod_list:
                return {"list": vod_list, "page": int(pg)}
        except Exception:
            pass  # 接口失败则回退到页面解析

        # 回退：静态搜索页面
        try:
            search_url = f"{BASE}/search.html?wd={quote(key)}"
            html = self._get_decoded_html(search_url)
            vod_list = self._parse_vod_cards(html)
            return {"list": vod_list, "page": int(pg)}
        except Exception:
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, video_id, vipFlags):
        try:
            html = self._get_decoded_html(video_id)
        except Exception:
            return {"parse": 0, "url": ""}
        m = re.search(r'var\s+player_\w+\s*=\s*({[^;]+})', html, re.DOTALL)
        if not m:
            direct = re.search(r'"url":"(https?://[^"]+\.(?:mp4|m3u8)[^"]*)"', html)
            return {"parse": 0, "url": direct.group(1)} if direct else {"parse": 0, "url": ""}
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            raw = m.group(1)
            fallback = re.search(r'"url":"(https?://[^"]+)"', raw)
            return {"parse": 0, "url": fallback.group(1)} if fallback else {"parse": 0, "url": ""}
        mp4_url = data.get("url", "")
        if data.get("encrypt") == 1 and data.get("from") in ("xfy2", "CS"):
            mp4_url = f"https://player.moedot.net/player/index.php?code=xfdm1&from=cf&url={mp4_url}"
            return {"parse": 1, "url": mp4_url}
        return {"parse": 0, "url": mp4_url}

    def getName(self):
        return "xifanacg"

    def destroy(self):
        if hasattr(self, "session"):
            self.session.close()