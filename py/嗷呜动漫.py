# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。
# junyouyun

import re
import sys
import json
import base64
import os
from Crypto.Cipher import AES

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.aowu.tv/'
    }

    HOST = 'https://www.aowu.tv'
    API = 'https://www.aowu.tv/api/site/secure'

    def init(self, extend=''):
        self.host = self.HOST
        self._aes_key = None

    # ===================== 密钥与加解密 =====================
    def _get_key(self):
        if self._aes_key:
            return self._aes_key
        try:
            resp = self.fetch(self.host, headers=self.headers)
            html = resp.text
        except Exception as e:
            raise RuntimeError(f"获取首页失败: {e}")

        meta = re.search(r'<meta[^>]+name=["\']?fk-p["\']?[^>]+content=["\']?([^"\'\s>]+)', html)
        meta = meta.group(1) if meta else ''
        fks = re.search(r'<html[^>]+data-fk-s=["\']?([^"\'\s>]+)', html)
        fks = fks.group(1) if fks else ''
        fkc = re.search(r'--fk-c:\s*"([^"]*)"', html)
        fkc = fkc.group(1) if fkc else ''
        fkm_match = re.search(r'__FKM\s*=\s*(\[.*?\])', html, re.DOTALL)
        try:
            fkm = json.loads(fkm_match.group(1)) if fkm_match else ['', '']
        except (json.JSONDecodeError, TypeError):
            fkm = ['', '']

        parts = [meta, fks, fkm[0] if len(fkm) > 0 else '', fkc, fkm[1] if len(fkm) > 1 else '']
        cleaned = [p.strip().strip("'\"") for p in parts]
        combined = ''.join(cleaned)

        try:
            key = base64.b64decode(combined)
        except Exception:
            key = combined.encode('latin-1')
        else:
            if len(key) not in (16, 24, 32):
                key = combined.encode('latin-1')

        if len(key) not in (16, 24, 32):
            if len(key) > 32:
                key = key[:32]
            elif len(key) > 24:
                key = key[:24]
            elif len(key) > 16:
                key = key[:16]
            else:
                key = key + b'\x00' * (16 - len(key))
        self._aes_key = key
        return key

    def _encrypt(self, plaintext):
        key = self._get_key()
        iv = os.urandom(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        return json.dumps({
            'n': base64.b64encode(iv).decode(),
            'd': base64.b64encode(ciphertext + tag).decode()
        })

    def _decrypt(self, enc_data):
        if isinstance(enc_data, str):
            enc_data = json.loads(enc_data)
        key = self._get_key()
        iv = base64.b64decode(enc_data['n'])
        ct_with_tag = base64.b64decode(enc_data['d'])
        tag = ct_with_tag[-16:]
        ciphertext = ct_with_tag[:-16]
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')

    def _post_api(self, body_dict):
        """发送加密 POST 请求并返回解密后的 dict"""
        enc_payload = self._encrypt(json.dumps(body_dict))
        # 部分框架的 fetch 支持 method/data 参数，否则回退到 requests
        try:
            resp = self.fetch(self.API, method='POST', data=enc_payload,
                              headers={'Content-Type': 'application/json'})
        except TypeError:
            import requests
            resp = requests.post(self.API, data=enc_payload,
                                 headers={**self.headers, 'Content-Type': 'application/json'},
                                 timeout=15)
        if hasattr(resp, 'json'):
            data = resp.json()
        else:
            data = json.loads(resp.text)
        decrypted = self._decrypt(data)
        return json.loads(decrypted)

    # ===================== 框架必需方法 =====================
    def homeContent(self, filter):
        """返回分类菜单"""
        classes = [
            {'type_name': '新番', 'type_id': '2'},
            {'type_name': '番剧', 'type_id': '1'},
            {'type_name': '剧场', 'type_id': '3'}
        ]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        """首页推荐（取新番第一页）"""
        data = self.categoryContent('2', '1', False, {})
        return {'list': data.get('list', [])}

    def categoryContent(self, tid, pg, filter, extend):
        """分类影片列表"""
        body = {
            'action': 'bundle',
            'params': {
                'key': str(tid),
                'type': '',
                'year': '',
                'sort': 'latest',
                'page': int(pg) if pg else 1,
                'limit': 12,
                'bundle_page': 'category'
            }
        }
        data = self._post_api(body)
        items = data.get('data', {}).get('data', {}).get('list', [])
        result = []
        for it in items:
            result.append({
                'vod_id': str(it['id']),
                'vod_name': it['name'],
                'vod_pic': it.get('pic', ''),
                'vod_remarks': it.get('remarks', ''),
                'vod_year': it.get('year', ''),
                'vod_area': it.get('area', ''),
                'vod_actor': it.get('actor', ''),
                'vod_director': it.get('director', ''),
                'vod_content': it.get('content', ''),
            })
        return {'list': result, 'page': pg}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        body = {
            'action': 'bundle',
            'params': {
                'anime': key,
                'page': int(pg) if pg else 1,
                'limit': 21,
                'bundle_page': 'search'
            }
        }
        try:
            data = self._post_api(body)
        except Exception:
            return {'list': [], 'page': pg}
        lst = data.get('data', {}).get('list') or data.get('data', {}).get('data', {}).get('list', [])
        result = []
        for it in lst:
            result.append({
                'vod_id': str(it['id']),
                'vod_name': it['name'],
                'vod_pic': it.get('pic', ''),
                'vod_remarks': it.get('remarks', ''),
                'vod_year': it.get('year', ''),
            })
        return {'list': result, 'page': pg}

    def detailContent(self, ids):
        """视频详情"""
        vid = ids[0] if isinstance(ids, list) else ids
        body = {
            'action': 'bundle',
            'params': {
                'id': int(vid),
                'bundle_page': 'video'
            }
        }
        data = self._post_api(body)
        detail = data.get('data', {}).get('data', {}).get('video', {})
        sources = data.get('data', {}).get('data', {}).get('sources', [])

        vod = {
            'vod_id': str(vid),
            'vod_name': detail.get('name', ''),
            'vod_pic': detail.get('pic', ''),
            'vod_actor': detail.get('actor', ''),
            'vod_director': detail.get('director', ''),
            'vod_remarks': detail.get('remarks', ''),
            'vod_year': detail.get('year', ''),
            'vod_area': detail.get('area', ''),
            'vod_content': detail.get('content', ''),
            'vod_play_from': [],
            'vod_play_url': []
        }

        for source in sources:
            if not source.get('episodes'):
                continue
            vod['vod_play_from'].append(source['name'])
            eps = []
            for ep in source['episodes']:
                param = f"{vid}|{source['id']}|{ep['no']}"
                eps.append(f"{ep['name']}${param}")
            vod['vod_play_url'].append('#'.join(eps))

        vod['vod_play_from'] = '$$$'.join(vod['vod_play_from'])
        vod['vod_play_url'] = '$$$'.join(vod['vod_play_url'])
        return {'list': [vod]}

    def playerContent(self, flag, video_id, vipFlags):
        """解析播放地址"""
        try:
            parts = video_id.split('|')
            if len(parts) != 3:
                return {'parse': 0, 'url': ''}
            vod_id, source_id, ep_no = parts

            # 第一步：获取 token
            body1 = {
                'action': 'bundle',
                'params': {
                    'id': int(vod_id),
                    'episode': int(ep_no),
                    'source_id': int(source_id),
                    'bundle_page': 'play'
                }
            }
            data1 = self._post_api(body1)
            token = data1.get('data', {}).get('data', {}).get('play_token', {}).get('token')
            if not token:
                return {'parse': 0, 'url': ''}

            # 第二步：获取真实播放地址
            body2 = {
                'action': 'play',
                'params': {
                    'id': int(vod_id),
                    'token': token
                }
            }
            data2 = self._post_api(body2)
            if data2.get('code') == 200 and data2.get('data', {}).get('url'):
                return {
                    'parse': 0,
                    'url': data2['data']['url'],
                    'header': self.headers
                }
            return {'parse': 0, 'url': ''}
        except Exception as e:
            print(f'[嗷呜动漫] 播放解析失败: {e}')
            return {'parse': 0, 'url': ''}

    # ===================== 辅助（可选） =====================
    def getName(self):
        return "嗷呜动漫"

    def destroy(self):
        pass