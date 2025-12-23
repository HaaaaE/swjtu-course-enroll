# main_gui.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.jwc import Enroller

class CourseGrabberGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("西南交大选课助手 v1.0")
        self.root.geometry("1000x650")
        
        self.config_file = "config.json"
        self.enroller1 = None  # jwc.swjtu.edu.cn
        self.enroller2 = None  # jiaowu.swjtu.edu.cn/TMS
        self.config = self.load_config()
        self.is_grabbing = False
        self.grab_thread = None
        
        self.setup_ui()
        self.update_status()
        self.load_course_list()
        
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("错误", f"加载配置文件失败: {e}")
                return {"username": "", "password": "", "courses": [], "max_workers": 20}
        return {"username": "", "password": "", "courses": [], "max_workers": 20}
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def setup_ui(self):
        """设置UI布局"""
        # === 账号登录区域 ===
        login_frame = ttk.LabelFrame(self.root, text="账号登录", padding="10")
        login_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 第一行：学号、密码、登录按钮
        row1 = ttk.Frame(login_frame)
        row1.pack(fill=tk.X)
        
        ttk.Label(row1, text="学号:").pack(side=tk.LEFT, padx=(0, 5))
        self.username_var = tk.StringVar(value=self.config.get("username", ""))
        ttk.Entry(row1, textvariable=self.username_var, width=20).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row1, text="密码:").pack(side=tk.LEFT, padx=(0, 5))
        self.password_var = tk.StringVar(value=self.config.get("password", ""))
        ttk.Entry(row1, textvariable=self.password_var, show="*", width=20).pack(side=tk.LEFT, padx=(0, 20))
        
        self.login_btn = ttk.Button(row1, text="登录", command=self.login, width=10)
        self.login_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_account_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="保存账号", variable=self.save_account_var).pack(side=tk.LEFT, padx=(0, 20))
        
        self.status_label = ttk.Label(row1, text="✗ 未登录", foreground="red", font=("", 10, "bold"))
        self.status_label.pack(side=tk.LEFT)
        
        # === 添加课程区域 ===
        add_frame = ttk.LabelFrame(self.root, text="添加课程", padding="10")
        add_frame.pack(fill=tk.X, padx=10, pady=5)
        
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X)
        
        ttk.Label(row2, text="选课编号:").pack(side=tk.LEFT, padx=(0, 5))
        self.teach_id_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.teach_id_var, width=15).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row2, text="备注:").pack(side=tk.LEFT, padx=(0, 5))
        self.remark_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.remark_var, width=30).pack(side=tk.LEFT, padx=(0, 20))
        
        self.need_book_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="需要教材", variable=self.need_book_var).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Button(row2, text="查询课程", command=self.search_course, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row2, text="添加到列表", command=self.add_course, width=12).pack(side=tk.LEFT)
        
        # === 中间区域：左边是课程列表，右边是日志 ===
        middle_frame = ttk.Frame(self.root)
        middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左侧：课程列表
        left_frame = ttk.LabelFrame(middle_frame, text="选课列表", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 创建表格
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("选课编号", "真实ID", "备注", "需要教材", "状态")
        self.course_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        
        # 设置列
        self.course_tree.heading("选课编号", text="选课编号")
        self.course_tree.heading("真实ID", text="真实ID")
        self.course_tree.heading("备注", text="备注")
        self.course_tree.heading("需要教材", text="需要教材")
        self.course_tree.heading("状态", text="状态")
        
        self.course_tree.column("选课编号", width=70, anchor=tk.CENTER)
        self.course_tree.column("真实ID", width=110, anchor=tk.CENTER)
        self.course_tree.column("备注", width=150, anchor=tk.W)
        self.course_tree.column("需要教材", width=70, anchor=tk.CENTER)
        self.course_tree.column("状态", width=70, anchor=tk.CENTER)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 列表操作按钮
        list_btn_frame = ttk.Frame(left_frame)
        list_btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(list_btn_frame, text="删除选中", command=self.remove_course).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(list_btn_frame, text="清除已选状态", command=self.clear_selected_status).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(list_btn_frame, text="刷新列表", command=self.load_course_list).pack(side=tk.LEFT)
        
        # 右侧：日志区域（分两列）
        right_frame = ttk.Frame(middle_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 左侧日志：系统日志
        system_log_frame = ttk.LabelFrame(right_frame, text="系统日志", padding="5")
        system_log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(system_log_frame, width=25, height=15, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 右侧日志：选课结果
        result_log_frame = ttk.LabelFrame(right_frame, text="选课结果", padding="5")
        result_log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.result_log_text = scrolledtext.ScrolledText(result_log_frame, width=25, height=15, state='disabled', wrap=tk.WORD)
        self.result_log_text.pack(fill=tk.BOTH, expand=True)
        
        # === 抢课控制区域 ===
        control_frame = ttk.LabelFrame(self.root, text="抢课控制", padding="10")
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        row3 = ttk.Frame(control_frame)
        row3.pack()
        
        ttk.Label(row3, text="重试间隔(秒):").pack(side=tk.LEFT, padx=(0, 5))
        self.interval_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(row3, from_=0.1, to=10, increment=0.1, textvariable=self.interval_var, width=10, format="%.1f").pack(side=tk.LEFT, padx=(0, 30))
        
        ttk.Label(row3, text="最大并发数量:").pack(side=tk.LEFT, padx=(0, 5))
        self.max_workers_var = tk.IntVar(value=self.config.get("max_workers", 20))
        ttk.Spinbox(row3, from_=1, to=100, increment=1, textvariable=self.max_workers_var, width=10).pack(side=tk.LEFT, padx=(0, 30))
        
        self.start_btn = ttk.Button(row3, text="开始抢课", command=self.start_grabbing, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(row3, text="停止抢课", command=self.stop_grabbing, width=12, state='disabled')
        self.stop_btn.pack(side=tk.LEFT)
        
    def log(self, message):
        """添加系统日志"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def result_log(self, message):
        """添加选课结果日志"""
        self.result_log_text.config(state='normal')
        self.result_log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.result_log_text.see(tk.END)
        self.result_log_text.config(state='disabled')
    
    def update_status(self):
        """更新登录状态"""
        status1 = "✓" if self.enroller1 and self.enroller1.is_logged_in else "✗"
        status2 = "✓" if self.enroller2 and self.enroller2.is_logged_in else "✗"
        
        if (self.enroller1 and self.enroller1.is_logged_in) or (self.enroller2 and self.enroller2.is_logged_in):
            self.status_label.config(text=f"{status1} URL1 | {status2} URL2", foreground="green")
        else:
            self.status_label.config(text="✗ 未登录", foreground="red")
    
    def login(self):
        """登录"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        
        if not username or not password:
            messagebox.showerror("错误", "学号或密码不能为空")
            return
        
        # 保存账号
        if self.save_account_var.get():
            self.config["username"] = username
            self.config["password"] = password
            self.save_config()
        
        self.log(f"正在使用账号 {username} 登录...")
        self.login_btn.config(state='disabled')
        
        def login_thread():
            try:
                # 登录 URL1: jwc.swjtu.edu.cn
                self.log("正在登录 URL1 (jwc.swjtu.edu.cn)...")
                self.enroller1 = Enroller(username, password, base="jwc.swjtu.edu.cn")
                success1 = self.enroller1.login()
                if success1:
                    self.log("✓ URL1 登录成功")
                else:
                    self.log("✗ URL1 登录失败")
                
                # 登录 URL2: jiaowu.swjtu.edu.cn/TMS
                self.log("正在登录 URL2 (jiaowu.swjtu.edu.cn/TMS)...")
                self.enroller2 = Enroller(username, password, base="jiaowu.swjtu.edu.cn/TMS")
                success2 = self.enroller2.login()
                if success2:
                    self.log("✓ URL2 登录成功")
                else:
                    self.log("✗ URL2 登录失败")
                
                if success1 or success2:
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"登录完成\nURL1: {'成功' if success1 else '失败'}\nURL2: {'成功' if success2 else '失败'}"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("失败", "两个URL都登录失败，请检查账号密码"))
            except Exception as e:
                self.log(f"✗ 登录异常: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"登录异常: {e}"))
            finally:
                self.root.after(0, self.update_status)
                self.root.after(0, lambda: self.login_btn.config(state='normal'))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def search_course(self):
        """查询课程"""
        enroller = self.enroller1 if (self.enroller1 and self.enroller1.is_logged_in) else self.enroller2
        if not enroller or not enroller.is_logged_in:
            messagebox.showerror("错误", "请先登录")
            return
        
        teach_id = self.teach_id_var.get().strip()
        if not teach_id:
            messagebox.showerror("错误", "请输入选课编号")
            return
        
        self.log(f"正在查询课程 {teach_id}...")
        
        def search_thread():
            try:
                success, real_teach_id, error = enroller.search_course_by_teach_id(teach_id)
                if success:
                    self.log(f"✓ 查询成功: {teach_id} -> {real_teach_id}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"选课编号: {teach_id}\n真实ID: {real_teach_id}"))
                else:
                    self.log(f"✗ 查询失败: {error}")
                    self.root.after(0, lambda: messagebox.showerror("失败", error))
            except Exception as e:
                self.log(f"✗ 查询异常: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"查询异常: {e}"))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def add_course(self):
        """添加课程到列表"""
        enroller = self.enroller1 if (self.enroller1 and self.enroller1.is_logged_in) else self.enroller2
        if not enroller or not enroller.is_logged_in:
            messagebox.showerror("错误", "请先登录")
            return
        
        teach_id = self.teach_id_var.get().strip()
        remark = self.remark_var.get().strip()
        
        if not teach_id:
            messagebox.showerror("错误", "请输入选课编号")
            return
        
        self.log(f"正在查询并添加课程 {teach_id}...")
        
        def add_thread():
            try:
                # 先查询获取真实ID
                success, real_teach_id, error = enroller.search_course_by_teach_id(teach_id)
                
                if not success:
                    self.log(f"✗ 查询失败: {error}")
                    self.root.after(0, lambda: messagebox.showerror("失败", f"查询失败: {error}"))
                    return
                
                # 检查是否已存在
                for course in self.config["courses"]:
                    if course["real_teach_id"] == real_teach_id:
                        self.log(f"课程 {teach_id} 已在列表中")
                        self.root.after(0, lambda: messagebox.showwarning("提示", f"课程 {teach_id} 已在列表中"))
                        return
                
                # 添加到列表
                course = {
                    "teach_id": teach_id,
                    "real_teach_id": real_teach_id,
                    "remark": remark,
                    "need_book": self.need_book_var.get(),
                    "selected": False
                }
                
                self.config["courses"].append(course)
                self.save_config()
                
                self.log(f"✓ 已添加课程: {teach_id} -> {real_teach_id} ({remark})")
                self.root.after(0, self.load_course_list)
                self.root.after(0, lambda: messagebox.showinfo("成功", f"已添加课程:\n{teach_id} -> {real_teach_id}"))
                
                # 清空输入框
                self.root.after(0, lambda: self.teach_id_var.set(""))
                self.root.after(0, lambda: self.remark_var.set(""))
                
            except Exception as e:
                self.log(f"✗ 添加课程异常: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"添加课程异常: {e}"))
        
        threading.Thread(target=add_thread, daemon=True).start()
    
    def load_course_list(self):
        """加载课程列表到表格"""
        # 清空表格
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        
        # 添加数据
        for course in self.config["courses"]:
            status = "✓已选上" if course["selected"] else "未选"
            book = "是" if course["need_book"] else "否"
            
            self.course_tree.insert("", tk.END, values=(
                course["teach_id"],
                course["real_teach_id"],
                course["remark"],
                book,
                status
            ))
    
    def remove_course(self):
        """删除选中的课程"""
        selected = self.course_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的课程")
            return
        
        if messagebox.askyesno("确认", "确定要删除选中的课程吗？"):
            for item in selected:
                values = self.course_tree.item(item)['values']
                real_teach_id = values[1]
                
                # 从配置中删除
                self.config["courses"] = [c for c in self.config["courses"] if c["real_teach_id"] != real_teach_id]
            
            self.save_config()
            self.load_course_list()
            self.log(f"✓ 已删除 {len(selected)} 门课程")
    
    def clear_selected_status(self):
        """清除已选状态"""
        if messagebox.askyesno("确认", "确定要清除所有课程的已选状态吗？"):
            for course in self.config["courses"]:
                course["selected"] = False
            self.save_config()
            self.load_course_list()
            self.log("✓ 已清除所有课程的已选状态")
    
    def start_grabbing(self):
        """开始抢课"""
        if not ((self.enroller1 and self.enroller1.is_logged_in) or (self.enroller2 and self.enroller2.is_logged_in)):
            messagebox.showerror("错误", "请先登录")
            return
        
        if not self.config["courses"]:
            messagebox.showerror("错误", "选课列表为空，请先添加课程")
            return
        
        self.is_grabbing = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # 保存最大并发数量设置
        max_workers = self.max_workers_var.get()
        self.config["max_workers"] = max_workers
        self.save_config()
        
        self.log("=== 开始抢课 ===")
        self.log(f"最大并发数量: {max_workers}")
        
        def grab_thread():
            round_num = 1
            interval = self.interval_var.get()
            
            def process_course(course, round_num, enroller, url_name):
                """处理单个课程在特定URL的选课请求"""
                if not self.is_grabbing:
                    return None
                
                # 执行前检查是否已选上
                if course.get("selected", False):
                    return None
                
                teach_id = course["teach_id"]
                real_teach_id = course["real_teach_id"]
                remark = course["remark"]
                need_book = course["need_book"]
                
                # 使用线程安全的方式记录"正在处理"日志
                self.root.after(0, lambda tid=teach_id, r=remark, rn=round_num, un=url_name: 
                                self.log(f"[第{rn}轮-{un}] 正在处理: {tid} ({r})"))
                
                try:
                    success, message = enroller.select_course(real_teach_id, need_book)
                    
                    if success:
                        self.root.after(0, lambda tid=teach_id, msg=message, rn=round_num, un=url_name: 
                                        self.result_log(f"[第{rn}轮-{un}] ✓ 选课成功: {tid} - {msg}"))
                        course["selected"] = True
                        self.save_config()
                        self.root.after(0, self.load_course_list)
                    else:
                        self.root.after(0, lambda tid=teach_id, msg=message, rn=round_num, un=url_name: 
                                        self.result_log(f"[第{rn}轮-{un}] ✗ 选课失败: {tid} - {msg}"))
                    
                    return success
                except Exception as e:
                    self.root.after(0, lambda tid=teach_id, err=str(e), rn=round_num, un=url_name: 
                                    self.result_log(f"[第{rn}轮-{un}] ✗ 选课异常: {tid} - {err}"))
                    return False
            
            # 创建持久的线程池
            executor = ThreadPoolExecutor(max_workers=max_workers)
            
            try:
                while self.is_grabbing:
                    # 筛选未选上的课程
                    pending_courses = [c for c in self.config["courses"] if not c["selected"]]
                    
                    if not pending_courses:
                        self.log("✓ 所有课程都已选上！")
                        break
                    
                    self.log(f"\n--- 第 {round_num} 轮抢课 ---")
                    self.log(f"待选课程数: {len(pending_courses)}，直接提交")
                    
                    # 对每门课程，同时向两个URL提交请求
                    for course in pending_courses:
                        if not self.is_grabbing:
                            break
                        # 提交到 URL1
                        if self.enroller1 and self.enroller1.is_logged_in:
                            executor.submit(process_course, course, round_num, self.enroller1, "URL1")
                        # 提交到 URL2
                        if self.enroller2 and self.enroller2.is_logged_in:
                            executor.submit(process_course, course, round_num, self.enroller2, "URL2")
                    
                    # 等待间隔后进入下一轮
                    round_num += 1
                    if self.is_grabbing:
                        self.log(f"等待 {interval} 秒后进入下一轮...")
                        time.sleep(interval)
            
            except Exception as e:
                self.log(f"✗ 抢课过程发生异常: {e}")
            
            finally:
                # 关闭线程池，等待所有任务完成
                executor.shutdown(wait=True)
                
                self.is_grabbing = False
                self.root.after(0, lambda: self.start_btn.config(state='normal'))
                self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
                self.log("=== 抢课已停止 ===")
        
        self.grab_thread = threading.Thread(target=grab_thread, daemon=True)
        self.grab_thread.start()
    
    def stop_grabbing(self):
        """停止抢课"""
        self.is_grabbing = False
        self.log("正在停止抢课...")
        self.stop_btn.config(state='disabled')

def main():
    root = tk.Tk()
    app = CourseGrabberGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()