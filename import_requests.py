# -*- coding: utf-8 -*-
"""
改进后的 import_requests.py

功能：
 - 从命令行或配置中读取目标网站和可选的 user-agent、用户名/密码。
 - 请求页面并用 BeautifulSoup 查找可能的验证码图片（基于常见关键字搜索）。
 - 下载验证码图片到临时文件，并尝试使用项目内的 neural_network 模型进行预测（如果存在并可加载）。
 - 提供两种点击策略：优先使用 Python 的 pyautogui（若可用），否则尝试调用同目录下已编译的 `Type_plus.exe`（如果存在）。
 - 对缺失依赖和不可运行情况做出友好提示，不抛出未捕获异常。

使用示例：
    python import_requests.py --url https://example.com/login --user-agent "..." --click-times 3

注意：把前端与 C++ 的直接 import（例如从 HTML 或 .cpp 导入）替换为通过参数或在运行时调用外部程序的方式。
"""

import argparse
import requests
from bs4 import BeautifulSoup
import tempfile
import os
import sys
import logging
import subprocess
import csv
from utils import answer
# 可选库：Pillow, torch, torchvision, pyautogui
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False

try:
    import torchvision.transforms as T
    TV_AVAILABLE = True
except Exception:
    TV_AVAILABLE = False

try:
    import pyautogui
    PYA_AVAILABLE = True
except Exception:
    PYA_AVAILABLE = False

# 从项目 neural_network.py 导入预测接口（如果存在）
MODEL_AVAILABLE = False
_model = None
try:
    # neural_network.py 中定义了 CNN 类和 predict 函数
    from neural_network import CNN, predict
    MODEL_AVAILABLE = True
except Exception:
    MODEL_AVAILABLE = False

# 可选：Flask + Selenium，用于从前端表单触发自动化（回退到 CLI 模式如果不可用）
FLASK_AVAILABLE = False
SELENIUM_AVAILABLE = False
try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False


LOG_LEVEL = os.environ.get('IMPORT_REQUESTS_LOG', 'INFO').upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format='[%(levelname)s] %(message)s')


def find_captcha_img_tag(soup: BeautifulSoup):
    """尝试在 soup 中找到可能的验证码图片标签，返回第一个匹配的 <img> 或 None。
    搜索策略：匹配 id/class/alt/src 中包含 'captcha','verif','code' 等关键字。
    """
    keywords = ['captcha', 'verif', 'vcode', 'code', 'security']
    imgs = soup.find_all('img')
    for img in imgs:
        attrs = ' '.join([str(img.get('id') or ''), str(img.get('class') or ''), str(img.get('alt') or ''), str(img.get('src') or '')]).lower()
        for kw in keywords:
            if kw in attrs:
                return img
    # 兜底：如果只有一张图片，也可能是验证码
    if len(imgs) == 1:
        return imgs[0]
    return None


def download_image(session, base_url, src):
    """根据 img 的 src（可能是相对路径）下载图片并返回本地临时文件路径."""
    # 处理相对 URL
    from urllib.parse import urljoin
    url = urljoin(base_url, src)
    logging.info(f'Downloading image: {url}')
    try:
        r = session.get(url, stream=True, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logging.error('下载图片失败: %s', e)
        return None
    fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(url)[1] or '.png')
    os.close(fd)
    try:
        with open(tmp_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        return tmp_path
    except Exception as e:
        logging.error('写入临时文件失败: %s', e)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return None


def try_predict_image(image_path):
    """如果模型可用则尝试使用模型预测图像，返回预测结果或 None。
    说明：模型输入预处理非常依赖训练时的 pipeline；此处做最小尝试并会给出警告。
    """
    if not MODEL_AVAILABLE:
        logging.info('neural_network 模块不可用，跳过模型预测')
        return None
    if not PIL_AVAILABLE:
        logging.info('Pillow 未安装，无法加载图片进行预测')
        return None
    if not TORCH_AVAILABLE:
        logging.info('PyTorch 未安装，无法运行模型预测')
        return None

    # 载入模型（寻找同目录下 cnn_model.pth）
    model_path = os.path.join(os.path.dirname(__file__), 'cnn_model.pth')
    model = CNN()
    if os.path.exists(model_path):
        try:
            model.load_state_dict(torch.load(model_path, map_location='cpu'))
            model.eval()
            logging.info('已加载模型：%s', model_path)
        except Exception as e:
            logging.error('加载模型失败：%s', e)
            return None
    else:
        logging.info('模型文件未找到 (%s)，跳过预测', model_path)
        return None

    # 基本预处理：加载为 RGB -> 转为 Tensor -> 归一化（这可能需按训练 pipeline 调整）
    try:
        img = Image.open(image_path).convert('RGB')
        # 尺寸未知：这里尝试将图片缩放到 (80, 32) 的示例尺寸（可按需调整）
        target_size = (80, 32)  # (W,H) 示例，具体取决于训练时的尺寸
        img = img.resize(target_size)
        if TV_AVAILABLE:
            transform = T.Compose([
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            tensor = transform(img).unsqueeze(0)
        else:
            # 手工转换为 tensor
            import numpy as np
            arr = ( ( (np.array(img) / 255.0).astype('float32') ).transpose(2, 0, 1) )
            tensor = torch.from_numpy(arr).unsqueeze(0)
        # 调用 predict（neural_network.predict 接受 model 和 image）
        pred = predict(model, tensor)
        logging.info('预测结果（原始张量输出索引或标签）：%s', pred)
        return pred
    except Exception as e:
        logging.error('预测时发生错误：%s', e)
        return None


def cnki_login(session: requests.Session, username: str, password: str, use_selenium: bool = False, driver=None, headers: dict = None) -> bool:
    """
    尝试登录中国知网（CNKI）。

    两种策略：
    - use_selenium=True 且已提供 selenium：使用浏览器自动化并把浏览器 cookie 同步回 requests.Session（更可靠，但需要 chromedriver）。
    - 否则：尝试用 requests 模拟表单提交（不保证能绕过验证码/JS 加密/反爬）。

    返回 True 表示登录成功（或至少获得了登录相关的 cookie），False 表示失败。

    注意：CNKI 有严格的反爬和验证码保护；如果遇到验证码或登录失败，请改用手工登录的浏览器会话并从浏览器导出 cookie。
    """
    login_urls = [
        'https://login.cnki.net/',
        'https://passport.cnki.net/',
        'https://kns.cnki.net/kns/login.aspx'
    ]
    headers = headers or {}

    if use_selenium and SELENIUM_AVAILABLE and driver is not None:
        try:
            # 打开登录页
            driver.get(login_urls[0])
            # 多策略查找用户名/密码输入框
            username_candidates = ['username', 'txtUserName', 'usernameInput', 'loginname', 'account']
            password_candidates = ['password', 'txtPassword', 'passwd', 'pwd']
            def fill(cands, value):
                for cand in cands:
                    try:
                        el = driver.find_element(By.ID, cand)
                        el.clear()
                        el.send_keys(value)
                        return True
                    except Exception:
                        pass
                    try:
                        el = driver.find_element(By.NAME, cand)
                        el.clear()
                        el.send_keys(value)
                        return True
                    except Exception:
                        pass
                return False

            fill(username_candidates, username)
            fill(password_candidates, password)
            # 尝试提交：查找登录按钮
            try:
                btns = driver.find_elements(By.XPATH, "//button|//input[@type='submit']|//a")
                for b in btns:
                    try:
                        text = b.text or b.get_attribute('value') or ''
                        if any(k in text.lower() for k in ('登录', 'login', 'sign in')):
                            driver.execute_script('arguments[0].click();', b)
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            # 等待若干秒以完成登录
            import time as _t
            _t.sleep(3)

            # 把浏览器 cookie 同步回 requests session
            for c in driver.get_cookies():
                session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
            # 简单检测：访问 CNKI 个人中心/或搜索页检查是否被认为已登录
            try:
                r = session.get('https://kns.cnki.net', headers=headers or {}, timeout=10)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            return True
        except Exception as e:
            logging.error('Selenium 登录 CNKI 失败：%s', e)
            return False

    # 非 selenium 的 requests 登录尝试（常常会因为 JS / 验证码失败）
    try:
        # 请求登录页获取可能的隐藏字段
        for url in login_urls:
            try:
                r = session.get(url, headers=headers or {}, timeout=10)
                if r.ok:
                    login_page = r.text
                    login_url = url
                    break
            except Exception:
                continue
        else:
            logging.warning('无法获取 CNKI 登录页（网络问题或被拦截）')
            return False

        soup = BeautifulSoup(login_page, 'html.parser')
        form = soup.find('form')
        data = {}
        action = login_url
        if form:
            if form.get('action'):
                from urllib.parse import urljoin
                action = urljoin(login_url, form.get('action'))
            # 收集隐藏字段
            for inp in form.find_all('input'):
                name = inp.get('name')
                if not name:
                    continue
                val = inp.get('value') or ''
                data[name] = val

        # 常见字段名尝试覆盖
        # 这些字段名可能不匹配，登录常常会失败
        for k in ('username', 'userName', 'txtUserName', 'account'):
            if k in data:
                data[k] = username
        for k in ('password', 'pwd', 'txtPassword'):
            if k in data:
                data[k] = password

        # 如果没有合适的字段，尝试一些常见的字段名
        if not any(k in data for k in ('username', 'userName', 'txtUserName', 'account')):
            data['username'] = username
        if not any(k in data for k in ('password', 'pwd', 'txtPassword')):
            data['password'] = password

        r2 = session.post(action, data=data, headers=headers or {}, timeout=10)
        if r2.ok:
            # 简单检查是否包含登录失败提示
            if '验证码' in r2.text or '登录失败' in r2.text or '验证码' in r2.url:
                logging.warning('登录响应中发现验证码或失败提示，requests 登录可能无法通过（需要交互或 Selenium）')
                return False
            return True
        return False
    except Exception as e:
        logging.error('requests 登录 CNKI 异常：%s', e)
        return False


def parse_cnki_results(html_text, max_results=10, session: requests.Session = None):
    """
    最小化解析 CNKI 搜索结果 HTML，返回字典列表：
    [{ 'title':..., 'authors':..., 'source':..., 'year':..., 'link':... }, ...]

    说明：CNKI 页面结构经常变化，此解析为通用的启发式解析，可能需要按需调整选择器。
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    results = []
    # 常见的结果容器：表格、div 列表、li 等。我们采集页面中所有可能的论文链接
    # 按启发式规则：查找所有 a 标签，href 包含 'Detail' 或 '/KCMS/detail/' 或 'kns'，文本较长可作为标题
    anchors = soup.find_all('a')
    seen = set()
    for a in anchors:
        href = a.get('href') or ''
        title = (a.get('title') or a.text or '').strip()
        if not href or not title:
            continue
        lower = href.lower()
        if any(k in lower for k in ('detail', '/kcms/detail', 'kns.cnki.net')) or len(title) > 6:
            # normalize absolute URL if possible
            from urllib.parse import urljoin
            url = urljoin('https://kns.cnki.net', href)
            # 解析最终可访问链接（尝试跟随重定向）
            final_url = url
            if session is not None:
                try:
                    # 先尝试 head 快速跟随重定向
                    r = session.head(url, allow_redirects=True, timeout=10)
                    final_url = getattr(r, 'url', url) or url
                except Exception:
                    try:
                        r = session.get(url, stream=True, allow_redirects=True, timeout=10)
                        final_url = getattr(r, 'url', url) or url
                        try:
                            r.close()
                        except Exception:
                            pass
                    except Exception:
                        final_url = url

            if final_url in seen:
                continue
            seen.add(final_url)
            # 尝试抓取邻近的作者/来源/年份信息
            parent = a.parent
            authors = None
            source = None
            year = None
            # 向外搜索同一行/同一父容器的文本
            if parent:
                text = parent.get_text(separator='|', strip=True)
                parts = [p for p in text.split('|') if p.strip()]
                # 依据经验：第一个长文本为标题，后面的可能包含作者/来源/年份
                if len(parts) >= 2:
                    # 过滤掉与标题重复的部分
                    extra = [p for p in parts if p not in (title, '')]
                    if extra:
                        # 粗略地把第一个 extra 看作作者/来源
                        authors = extra[0]
                        if len(extra) >= 2:
                            source = extra[1]
            # 尝试在 a 的祖先中查找包含年份的文本
            anc = a
            for _ in range(3):
                if not anc:
                    break
                txt = anc.get_text() if hasattr(anc, 'get_text') else ''
                import re
                m = re.search(r'20\d{2}|19\d{2}', txt)
                if m:
                    year = m.group(0)
                    break
                anc = getattr(anc, 'parent', None)

            results.append({'title': title, 'authors': authors, 'source': source, 'year': year, 'link': final_url})
            if len(results) >= max_results:
                break
    return results


def search_cnki(session: requests.Session, topic: str, max_results: int = 10, use_selenium: bool = False, driver=None, headers: dict = None):
    """
    在中国知网（CNKI）中按主题搜索论文，返回 parse_cnki_results 的结果列表。

    参数：
      - session: requests.Session 实例（如果使用 selenium 并希望复用 cookies，可先将 session 的 cookies 与浏览器同步）
      - topic: 要搜索的主题字符串
      - max_results: 最大返回条目数
      - use_selenium: 是否优先使用 Selenium（更可靠但需要 chromedriver 并可能需要人工登录）

    返回: list[dict]
    """
    headers = headers or {}
    # 优先使用 Selenium（若可用）
    if use_selenium and SELENIUM_AVAILABLE and driver is not None:
        try:
            # 打开 CNKI 简略搜索页
            driver.get('https://kns.cnki.net/kns/brief/Default_Result.aspx')
            # 尝试找到搜索框并输入
            possible = ['txt_SearchText', 'txt_1_value1', 'txtKey']
            filled = False
            for name in possible:
                try:
                    el = driver.find_element(By.ID, name)
                    el.clear()
                    el.send_keys(topic)
                    el.send_keys(Keys.ENTER)
                    filled = True
                    break
                except Exception:
                    pass
            if not filled:
                try:
                    el = driver.find_element(By.NAME, 'txt_1_value1')
                    el.clear()
                    el.send_keys(topic)
                    el.send_keys(Keys.ENTER)
                except Exception:
                    # 兜底：在 URL 中拼接 Query
                    from urllib.parse import quote_plus
                    q = quote_plus(topic)
                    driver.get(f'https://kns.cnki.net/kns/brief/Default_Result.aspx?Query=%E4%B8%BB%E9%A2%98%3D{q}')

            import time as _t
            _t.sleep(2)
            html = driver.page_source
            # 同步 cookie 到 requests session
            for c in driver.get_cookies():
                session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
            return parse_cnki_results(html, max_results=max_results, session=session)
        except Exception as e:
            logging.error('Selenium 搜索 CNKI 失败：%s', e)

    # 使用 requests 的简单 GET 搜索（可能被拦截或返回登录页）
    try:
        from urllib.parse import quote_plus
        q = quote_plus(topic)
        # 这是一个常见的简略检索 URL 模板（不同库和数据库可能需要调整）
        url = f'https://kns.cnki.net/kns/brief/Default_Result.aspx?Query=%E4%B8%BB%E9%A2%98%3D{q}&CurPage=1&RecordsPerPage={max_results}'
        r = session.get(url, headers=headers or {}, timeout=10)
        if r.status_code != 200:
            logging.warning('请求 CNKI 搜索页返回状态：%s', r.status_code)
            return []
        # 若被重定向到登录页或返回包含验证码提示，应作为失败处理
        text = r.text
        if '登录' in text and ('验证码' in text or '请登录' in text):
            logging.warning('搜索返回登录/验证码页面，可能需要先登录或使用 Selenium 浏览器会话')
            return []
        return parse_cnki_results(text, max_results=max_results, session=session)
    except Exception as e:
        logging.error('requests 搜索 CNKI 异常：%s', e)
        return []


def python_clicker(times=1, interval=0.1):
    """使用 pyautogui 进行点击（如果可用）"""
    if not PYA_AVAILABLE:
        logging.info('pyautogui 未安装，无法使用 Python 点击；请安装或提供 Type_plus.exe')
        return False
    try:
        for _ in range(times):
            pyautogui.click()
            pyautogui.sleep(interval)
        return True
    except Exception as e:
        logging.error('pyautogui 点击失败：%s', e)
        return False


def exe_clicker(times=1, interval=100):
    """尝试调用同目录下的 Type_plus.exe（或 Type_plus）来进行点击。
    约定：可执行文件接收两个可选参数：次数和间隔毫秒（如果可用）
    """
    exe_names = ['Type_plus.exe', 'Type_plus']
    for name in exe_names:
        path = os.path.join(os.path.dirname(__file__), name)
        if os.path.exists(path):
            try:
                cmd = [path, str(times), str(interval)]
                logging.info('调用可执行文件执行点击：%s', cmd)
                subprocess.Popen(cmd)
                return True
            except Exception as e:
                logging.error('调用可执行文件失败：%s', e)
                return False
    logging.info('未找到可调用的 C++ 可执行文件（Type_plus.exe）')
    return False


def app(argv=None):
    """程序化可调用的入口函数。默认从 sys.argv 读取参数；传入 argv 列表可用于在代码中调用。

    返回：当以函数方式调用时，返回 None 或查询结果列表（当使用 --cnki-topic 时）。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', '-u', required=False, help='目标 URL，例如 https://example.com/login（非必需，如果使用 --cnki-topic 则可省略）')
    parser.add_argument('--user-agent', '-a', dest='user_agent', default=None, help='可选 User-Agent 字符串')
    parser.add_argument('--click-times', type=int, default=1, help='预测成功后要执行的点击次数（默认1）')
    parser.add_argument('--click-interval-ms', type=int, default=100, help='点击间隔毫秒（用于 exe 点击器）')
    parser.add_argument('--use-pyautogui', action='store_true', help='优先使用 pyautogui 进行点击（若安装）')
    # CNKI 相关选项
    parser.add_argument('--cnki-topic', type=str, default=None, help='在中国知网(CNKI)中要检索的主题字符串')
    parser.add_argument('--cnki-username', type=str, default=None, help='用于尝试登录 CNKI 的用户名（可选）')
    parser.add_argument('--cnki-password', type=str, default=None, help='用于尝试登录 CNKI 的密码（可选）')
    parser.add_argument('--cnki-use-selenium', action='store_true', help='在 CNKI 登录/搜索时优先使用 Selenium 浏览器（若可用）')
    parser.add_argument('--save-csv', type=str, default=None, help='如果指定，将把 CNKI 检索结果保存为 CSV（只作用于 --cnki-topic）')
    args = parser.parse_args(argv)

    if not args.url and not args.cnki_topic:
        parser.error('必须指定 --url 或 --cnki-topic 之一')

    session = requests.Session()
    headers = {}
    if args.user_agent:
        headers['User-Agent'] = args.user_agent
    # 如果用户提供了 cnki-topic，走 CNKI 登录/搜索流程
    if args.cnki_topic:
        driver = None
        try:
            logged = False
            # 首先尝试无浏览器的 requests 登录（如果提供了用户名/密码）
            if args.cnki_username and args.cnki_password:
                logged = cnki_login(session, args.cnki_username, args.cnki_password, use_selenium=False, headers=headers)
                if not logged:
                    logging.info('requests 登录 CNKI 未成功')
            # 如果指定了使用 Selenium，则启动浏览器；支持自动填写（提供用户名/密码）或手动登录后继续
            if args.cnki_use_selenium and SELENIUM_AVAILABLE:
                try:
                    chrome_options = Options()
                    chrome_options.add_argument('--no-sandbox')
                    if args.user_agent:
                        chrome_options.add_argument(f'user-agent={args.user_agent}')
                    driver = webdriver.Chrome(options=chrome_options)
                    # 如果提供了用户名/密码，尝试自动登录
                    if args.cnki_username and args.cnki_password:
                        logged = cnki_login(session, args.cnki_username, args.cnki_password, use_selenium=True, driver=driver, headers=headers)
                    else:
                        # 提示用户在弹出的浏览器中手动登录，然后回到终端按回车继续
                        print('浏览器已打开，请在打开的浏览器中手动完成 CNKI 登录，然后回到此终端按回车继续...')
                        try:
                            input()
                        except Exception:
                            # 在某些环境中 input 可能不工作，尝试等待固定时间
                            import time as _t
                            _t.sleep(5)
                        # 登录后把 cookie 同步回 session
                        for c in driver.get_cookies():
                            session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
                        logged = True
                except Exception as e:
                    logging.error('启动 Selenium 或使用 Selenium 登录时出错：%s', e)

            # 执行搜索
            results = search_cnki(session, args.cnki_topic, max_results=20, use_selenium=(args.cnki_use_selenium and driver is not None), driver=driver, headers=headers)
            if not results:
                logging.info('未找到结果或被拦截（可能需要先手动在浏览器登录 CNKI）')
            else:
                for i, r in enumerate(results, 1):
                    print(f"{i}. {r.get('title')}")
                    print(f"   authors: {r.get('authors')}")
                    print(f"   source: {r.get('source')} year: {r.get('year')}")
                    print(f"   link: {r.get('link')}")
                    print('')
                # 保存为 CSV（如果用户请求）
                if args.save_csv:
                    try:
                        keys = ['title', 'authors', 'source', 'year', 'link']
                        with open(args.save_csv, 'w', newline='', encoding='utf-8') as _f:
                            writer = csv.DictWriter(_f, fieldnames=keys)
                            writer.writeheader()
                            for it in results:
                                row = {k: (it.get(k) or '') for k in keys}
                                writer.writerow(row)
                        logging.info('已将结果保存到 CSV: %s', args.save_csv)
                    except Exception as e:
                        logging.error('保存 CSV 失败: %s', e)
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
        return results

    # 如果没有使用 CNKI 搜索，则保持原有的页面验证码处理逻辑（需要 --url）
    try:
        r = session.get(args.url, headers=headers, timeout=10)
    except Exception as e:
        logging.error('请求失败：%s', e)
        sys.exit(1)

    if not r.ok:
        logging.error('HTTP 错误：%s', r.status_code)
        sys.exit(1)

    soup = BeautifulSoup(r.text, 'html.parser')
    img_tag = find_captcha_img_tag(soup)
    if not img_tag:
        logging.info('未在页面中找到明显的验证码图片（请根据目标页面调整选择器）')
        sys.exit(0)

    src = img_tag.get('src')
    if not src:
        logging.info('找到的 img 标签没有 src 属性，无法下载')
        sys.exit(0)

    img_path = download_image(session, args.url, src)
    if not img_path:
        logging.info('下载验证码图片失败，停止')
        sys.exit(0)

    logging.info('验证码已保存到：%s', img_path)

    # 尝试用模型预测
    pred = try_predict_image(img_path)

    # 如果预测成功或不需要预测，执行点击动作（这里只是示例：真实点击位置需要更具体的定位）
    clicked = False
    if args.use_pyautogui:
        clicked = python_clicker(times=args.click_times, interval=args.click_interval_ms/1000.0)
    if not clicked:
        # 试着调用 exe 点击器（间隔以毫秒传入）
        clicked = exe_clicker(times=args.click_times, interval=args.click_interval_ms)

    if clicked:
        logging.info('点击动作已发出（不保证页面上元素被正确点击，需结合可视化定位或自动化工具）')
    else:
        logging.info('未执行任何点击。请安装 pyautogui 或在同目录提供可执行点击程序（Type_plus.exe）')

    # 清理临时图片
    try:
        os.remove(img_path)
    except Exception:
        pass


if __name__ == '__main__':
    # 支持两种运行方式：
    # 1) 命令行模式（默认）：python import_requests.py --url ...
    # 2) 启动 Flask 服务以供前端提交：python import_requests.py --serve
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--serve', action='store_true', help='以 Flask 服务模式启动，监听 127.0.0.1:5000，处理前端提交')
    known, _ = parser.parse_known_args()
    if known.serve:
        if not FLASK_AVAILABLE:
            logging.error('Flask 未安装，无法以服务模式启动。请安装 flask: pip install flask')
            sys.exit(1)
        flask_app = Flask(__name__)

        @flask_app.route('/run', methods=['POST'])
        def run_from_frontend():
            # 接收前端表单字段并尝试用 Selenium 执行自动化（若可用）
            url = request.form.get('Website') or request.form.get('url') or request.form.get('url')
            user_agent = request.form.get('USERAGENT') or request.form.get('user_agent')
            username = request.form.get('Username') or request.form.get('username')
            password = request.form.get('Password') or request.form.get('password')
            want = request.form.get('Want') or request.form.get('want')
            click_times = int(request.form.get('click_times') or request.form.get('click-times') or 1)

            if not url:
                return jsonify({'error': '缺少 url 参数'}), 400

            if SELENIUM_AVAILABLE:
                try:
                    chrome_options = Options()
                    chrome_options.add_argument('--no-sandbox')
                    if user_agent:
                        chrome_options.add_argument(f'user-agent={user_agent}')
                    driver = webdriver.Chrome(options=chrome_options)
                    driver.get(url)

                    # 如果提供了用户名/密码，尝试查找输入框并填写（基于常见属性）
                    def try_fill_input(name_candidates, value):
                        """多策略查找输入框并填写：name, id, placeholder, aria-label, css selector, type 等"""
                        for cand in name_candidates:
                            # by name
                            try:
                                el = driver.find_element(By.NAME, cand)
                                el.clear()
                                el.send_keys(value)
                                return True
                            except Exception:
                                pass
                            # by id
                            try:
                                el = driver.find_element(By.ID, cand)
                                el.clear()
                                el.send_keys(value)
                                return True
                            except Exception:
                                pass
                            # by placeholder
                            try:
                                el = driver.find_element(By.XPATH, f"//input[contains(@placeholder, '{cand}')]")
                                el.clear()
                                el.send_keys(value)
                                return True
                            except Exception:
                                pass
                            # by aria-label
                            try:
                                el = driver.find_element(By.XPATH, f"//input[contains(@aria-label, '{cand}')]")
                                el.clear()
                                el.send_keys(value)
                                return True
                            except Exception:
                                pass
                            # by type (email/user/password)
                            try:
                                if cand in ('email', 'user', 'username'):
                                    el = driver.find_element(By.XPATH, "//input[@type='email']")
                                    el.clear()
                                    el.send_keys(value)
                                    return True
                            except Exception:
                                pass
                        # 最后尝试第一个 text 或 email input
                        try:
                            el = driver.find_element(By.XPATH, "(//input[@type='text' or @type='email'])[1]")
                            el.clear()
                            el.send_keys(value)
                            return True
                        except Exception:
                            return False

                    user_name_candidates = ['username', 'user', 'email', 'login']
                    password_candidates = ['password', 'pass', 'passwd']

                    if username:
                        try_fill_input(user_name_candidates, username)
                    if password:
                        try_fill_input(password_candidates, password)

                    # 查找可能的提交按钮，基于按钮文本或常见 class/name 或 input[type=submit]
                    try:
                        texts = ['登录', 'login', 'sign in', 'submit', '登 录', '提交']
                        found = []
                        for t in texts:
                            # case-insensitive match on text content
                            els = driver.find_elements(By.XPATH, f"//*[self::button or self::a or self::input][contains(translate(normalize-space(string(.)), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{t}')]")
                            found += els
                        # 按类型 fallback
                        if not found:
                            found = driver.find_elements(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                        # 再按常见 class/id 名称尝试
                        if not found:
                            possible_btn_names = ['login', 'submit', 'button', 'signin', 'sign-in']
                            for name in possible_btn_names:
                                try:
                                    els = driver.find_elements(By.XPATH, f"//button[contains(@class, '{name}')] | //input[contains(@class, '{name}')] | //a[contains(@class, '{name}')] | //button[@id='{name}']")
                                    if els:
                                        found += els
                                except Exception:
                                    pass
                        if found:
                            btn = found[0]
                            for i in range(click_times):
                                try:
                                    driver.execute_script("arguments[0].click();", btn)
                                except Exception:
                                    try:
                                        btn.click()
                                    except Exception:
                                        logging.warning('点击按钮失败，尝试页面点击作为兜底')
                                # 小间隔
                                import time as _t
                                _t.sleep(0.3)
                            return jsonify({'status': 'clicked', 'element_type': 'button'})
                    except Exception as e:
                        logging.error('Selenium 点击过程出错: %s', e)

                    # 兜底：尝试点击页面上所有可点击元素（谨慎）
                    try:
                        clickable = driver.find_elements(By.XPATH, "//a | //button | //input[@type='button'] | //input[@type='submit']")
                        if clickable:
                            for i in range(click_times):
                                try:
                                    driver.execute_script('arguments[0].click();', clickable[0])
                                except Exception:
                                    pass
                                import time as _t
                                _t.sleep(0.3)
                            return jsonify({'status': 'clicked', 'element_type': 'first_clickable'})
                    except Exception as e:
                        logging.error('Selenium 兜底点击失败: %s', e)

                    driver.quit()
                    return jsonify({'status': 'no_click', 'reason': 'no_button_found'})
                except Exception as e:
                    logging.error('Selenium 自动化失败: %s', e)
                    return jsonify({'error': 'selenium_failed', 'detail': str(e)}), 500
            else:
                # 如果 selenium 不可用，回退到原 CLI 流程：直接请求页面并做解析/下载/预测
                # 这里直接调用 main 的逻辑会比较复杂；为简洁我们做一个简单请求并返回提示
                try:
                    session = requests.Session()
                    headers = {}
                    if user_agent:
                        headers['User-Agent'] = user_agent
                    r = session.get(url, headers=headers, timeout=10)
                    if not r.ok:
                        return jsonify({'error': 'http_error', 'code': r.status_code}), 502
                    soup = BeautifulSoup(r.text, 'html.parser')
                    img_tag = find_captcha_img_tag(soup)
                    if img_tag and img_tag.get('src'):
                        img_path = download_image(session, url, img_tag.get('src'))
                        return jsonify({'status': 'image_downloaded', 'path': img_path})
                    return jsonify({'status': 'no_image_found'})
                except Exception as e:
                    logging.error('回退请求流程失败: %s', e)
                    return jsonify({'error': 'fallback_failed', 'detail': str(e)}), 500

        @flask_app.route('/health', methods=['GET'])
        def health():
            return jsonify({'status': 'ok', 'selenium': SELENIUM_AVAILABLE, 'model': MODEL_AVAILABLE})

        logging.info('启动 Flask 服务： http://127.0.0.1:5000 ，将接收前端表单并尝试执行自动化')
        # 使用 threaded=True 以便并发处理请求
        flask_app.run(host='127.0.0.1', port=5000, threaded=True)
    else:
        # 以脚本方式运行，等同于 main()
        app()

