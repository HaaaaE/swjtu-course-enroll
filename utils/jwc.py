# utils/jwc.py
import requests
from bs4 import BeautifulSoup
import time
import logging
from urllib.parse import urlparse

from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import ocr  # 导入自定义OCR模块


class Enroller:
    def __init__(self, username, password, base="jwc.swjtu.edu.cn"):
        self.username = username
        self.password = password
        
        # 检测并设置 BASE_URL
        base_url = f"https://{base}"
        try:
            print(f"开始测试请求连通性和协议: " + f"{base_url}/service/login.html")
            response = requests.get(f"{base_url}/service/login.html", timeout=5, allow_redirects=True, verify=True)
            
            # 输出重定向信息
            if response.history:
                print(f"\n重定向路径 ({len(response.history)} 次):")
                for i, resp in enumerate(response.history, 1):
                    status = resp.status_code
                    from_url = resp.url
                    to_url = resp.headers.get('location', resp.url)
                    print(f"  {i}. [{status}] {from_url}")
                    print(f"     重定向到: {to_url}")
            
            print(f"最终URL: {response.url}")
            
            parsed = urlparse(response.url)
            if parsed.scheme == "http":
                base_url = f"http://{base}"
                print("检测到教务使用 HTTP，已切换为 HTTP 访问。")
                
        except Exception as e:
            print(f"协议检测失败: {e}，使用默认 HTTPS")
        
        # 设置所有 URL
        self.base_url = base_url
        self.login_page_url = f"{base_url}/service/login.html"
        self.login_api_url = f"{base_url}/vatuu/UserLoginAction"
        self.captcha_url = f"{base_url}/vatuu/GetRandomNumberToJPEG"
        self.loading_url = f"{base_url}/vatuu/UserLoadingAction"
        self.course_url = f"{base_url}/vatuu/CourseStudentAction"
    
        # 设置 session 和 headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Origin': base_url,
        })
        self.is_logged_in = False

    def login(self, max_retries=10, retry_delay=1):
        for attempt in range(1, max_retries + 1):
            print(f"--- 登录尝试 #{attempt}/{max_retries} ---")
            
            try:
                # 1. 获取并识别验证码
                print("正在获取验证码...")
                captcha_params = {'test': int(time.time() * 1000)}
                response = self.session.get(self.captcha_url, params=captcha_params, timeout=10)
                response.raise_for_status()
                captcha_code = ocr.classify(response.content)
                print(f"OCR 识别结果: {captcha_code}")
                if not captcha_code or len(captcha_code) != 4:
                    print("验证码识别失败，跳过本次尝试。")
                    if attempt < max_retries: time.sleep(retry_delay)
                    continue

                # 2. 尝试API登录
                print("正在尝试登录API...")
                login_payload = { 'username': self.username, 'password': self.password, 'ranstring': captcha_code, 'url': '', 'returnType': '', 'returnUrl': '', 'area': '' }
                response = self.session.post(self.login_api_url, data=login_payload, headers={'Referer': self.login_page_url}, timeout=10)
                response.raise_for_status()
                login_result = response.json()

                if login_result.get('loginStatus') == '1':
                    print(f"API验证成功！{login_result.get('loginMsg')[0:5]}")
                    print("正在访问加载页面以建立完整会话...")
                    self.session.get(self.loading_url, headers={'Referer': self.login_page_url}, timeout=10)
                    print("会话建立成功，已登录。")
                    self.is_logged_in = True
                    return True
                else:
                    print(f"登录API失败: {login_result.get('loginMsg', '未知错误')}")
            
            except Exception as e:
                print(f"登录过程中发生异常: {e}")

            if attempt < max_retries:
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
        
        print(f"\n登录失败 {max_retries} 次，程序终止。")
        return False
        
    def search_course_by_teach_id(self, teach_id):
        """
        按选课编号查询课程，获取真正的课程ID
        Args:
            teach_id: 选课编号
        Returns:
            tuple: (success, real_teach_id, error_message)
        """
        try:
            payload = {
                "setAction": "studentCourseSysSchedule",
                "viewType": "",
                "jumpPage": "1",
                "selectAction": "TeachID",
                "key1": teach_id,
                "courseType": "all",
                "key4": "",
                "btn": "执行查询"
            }
            
            response = self.session.post(
                self.course_url,
                data=payload,
                headers={'Referer': self.course_url},
                timeout=10
            )
            response.raise_for_status()
            
            # 解析HTML，提取真正的teachId
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找包含teachIdChooseBxxxx这样的span标签
            teach_id_pattern = f"teachIdChoose{teach_id}"
            teach_id_span = soup.find('span', id=teach_id_pattern)
            
            if teach_id_span and teach_id_span.text:
                real_teach_id = teach_id_span.text.strip()
                print(f"找到课程: {teach_id} -> 真实ID: {real_teach_id}")
                return True, real_teach_id, None
            
            # 如果没有找到，检查是否没有该课程
            no_results = soup.find('td', string=lambda x: x and '共有记录[0]条' in x)
            if no_results:
                return False, None, f"未找到选课编号为 {teach_id} 的课程"
            
            return False, None, "无法解析课程信息"
            
        except Exception as e:
            return False, None, f"查询课程失败: {str(e)}"
    def select_course(self, real_teach_id, need_book=True):
        try:
            params = {
                "setAction": "addStudentCourseApply",
                "teachId": real_teach_id,
                "isBook": "1" if need_book else "0",
                "tt": int(time.time() * 1000)
            }
            
            response = self.session.get(
                self.course_url,
                params=params,
                headers={'Referer': self.course_url},
                timeout=60
            )
            response.raise_for_status()
            
            import re
            results = re.findall(r'<!\[CDATA\[(.*?)\]\]>', response.text)
            
            if len(results) >= 2:
                return results[0] == "1", results[1]
            
            return False, "选课响应格式错误"
            
        except Exception as e:
            return False, f"选课请求失败: {str(e)}"

    def auto_select_course(self, teach_id, need_book=True):
        """
        自动选课：先搜索再选课
        Args:
            teach_id: 选课编号
            need_book: 是否需要教材
        Returns:
            tuple: (success, message)
        """
        if not self.is_logged_in:
            return False, "请先登录"
        
        print(f"开始处理选课编号: {teach_id}")
        
        # 1. 搜索课程获取真实ID
        success, real_teach_id, error = self.search_course_by_teach_id(teach_id)
        if not success:
            return False, error
        
        # 2. 提交选课请求
        print(f"正在提交选课请求，课程真实ID: {real_teach_id}")
        select_success, select_message = self.select_course(real_teach_id, need_book)
        
        return select_success, select_message

if __name__ == "__main__":
    pass