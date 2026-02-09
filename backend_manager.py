"""
Backend Manager - 图形化管理界面
功能：端口管理、模型切换、文档浏览、后端控制
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess
import threading
import time
import os
import requests
from pathlib import Path
import webbrowser
from dotenv import load_dotenv

class BackendManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Backend Manager v2.1")
        self.root.geometry("1000x700")

        # 后端进程
        self.backend_process = None
        self.is_running = False

        # 加载环境变量
        load_dotenv()

        # 创建界面
        self.create_widgets()

        # 初始化状态
        self.update_status()

    def create_widgets(self):
        # === 顶部：标题栏 ===
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill='x')

        title = ttk.Label(header, text="Backend Manager", font=("Arial", 16, "bold"))
        title.pack(side='left')

        self.status_label = ttk.Label(header, text="● 未连接", foreground="red", font=("Arial", 12))
        self.status_label.pack(side='right')

        # === 主要内容区 ===
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # 左侧面板
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side='left', fill='y', padx=(0, 5))

        # 右侧面板（文档浏览）
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='right', fill='both', expand=True)

        # === 左侧：控制面板 ===

        # 1. 后端控制
        backend_frame = ttk.LabelFrame(left_panel, text="后端控制", padding=10)
        backend_frame.pack(fill='x', pady=(0, 10))

        self.btn_start = ttk.Button(backend_frame, text="▶ 启动后端", command=self.start_backend)
        self.btn_start.pack(fill='x', pady=2)

        self.btn_stop = ttk.Button(backend_frame, text="⏹ 停止后端", command=self.stop_backend, state='disabled')
        self.btn_stop.pack(fill='x', pady=2)

        self.btn_test = ttk.Button(backend_frame, text="🔍 测试连接", command=self.test_connection)
        self.btn_test.pack(fill='x', pady=2)

        # 2. 端口管理
        port_frame = ttk.LabelFrame(left_panel, text="端口管理 (8000)", padding=10)
        port_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(port_frame, text="检查端口", command=self.check_port).pack(fill='x', pady=2)
        ttk.Button(port_frame, text="清理端口", command=self.clear_port).pack(fill='x', pady=2)

        self.port_status = ttk.Label(port_frame, text="未检查", foreground="gray")
        self.port_status.pack(pady=5)

        # 3. 模型配置
        model_frame = ttk.LabelFrame(left_panel, text="模型配置", padding=10)
        model_frame.pack(fill='x', pady=(0, 10))

        # 模型选择
        ttk.Label(model_frame, text="当前模型:").pack(anchor='w')
        self.model_var = tk.StringVar(value=os.getenv('USE_AZURE', 'false'))

        model_options = [
            ("Azure OpenAI (gpt-5-nano)", "true"),
            ("本地 Ollama", "false"),
        ]

        for text, value in model_options:
            ttk.Radiobutton(
                model_frame,
                text=text,
                variable=self.model_var,
                value=value,
                command=self.on_model_change
            ).pack(anchor='w', pady=2)

        ttk.Button(model_frame, text="💾 保存配置", command=self.save_model_config).pack(fill='x', pady=(10, 0))

        # 当前配置显示
        config_frame = ttk.LabelFrame(left_panel, text="当前配置", padding=10)
        config_frame.pack(fill='x', pady=(0, 10))

        self.config_text = tk.Text(config_frame, height=6, width=30, font=("Consolas", 9))
        self.config_text.pack(fill='x')
        self.update_config_display()

        # 4. 日志输出
        log_frame = ttk.LabelFrame(left_panel, text="运行日志", padding=10)
        log_frame.pack(fill='both', expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=30, font=("Consolas", 8))
        self.log_text.pack(fill='both', expand=True)

        # === 右侧：文档浏览 ===
        doc_frame = ttk.LabelFrame(right_panel, text="文档浏览", padding=10)
        doc_frame.pack(fill='both', expand=True)

        # 文档列表
        doc_list_frame = ttk.Frame(doc_frame)
        doc_list_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(doc_list_frame, text="选择文档:").pack(anchor='w')

        self.doc_listbox = tk.Listbox(doc_list_frame, height=6)
        self.doc_listbox.pack(fill='x', pady=5)
        self.doc_listbox.bind('<<ListboxSelect>>', self.on_doc_select)

        # 加载文档列表
        self.load_documents()

        # 文档内容显示
        doc_content_frame = ttk.Frame(doc_frame)
        doc_content_frame.pack(fill='both', expand=True)

        ttk.Button(doc_content_frame, text="📖 在浏览器中打开", command=self.open_in_browser).pack(anchor='e', pady=(0, 5))

        self.doc_content = scrolledtext.ScrolledText(doc_content_frame, wrap='word', font=("Consolas", 10))
        self.doc_content.pack(fill='both', expand=True)

        # === 底部：状态栏 ===
        status_frame = ttk.Frame(self.root, padding=5)
        status_frame.pack(fill='x', side='bottom')

        self.log_message("Backend Manager 已启动", "info")

    # === 后端控制 ===
    def start_backend(self):
        if self.is_running:
            messagebox.showwarning("警告", "后端已在运行中")
            return

        self.log_message("正在启动后端...", "info")

        def run_backend():
            try:
                self.backend_process = subprocess.Popen(
                    ['python', 'Main.py'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                self.is_running = True
                self.root.after(0, self.on_backend_started)

                # 实时读取日志
                for line in self.backend_process.stdout:
                    self.root.after(0, lambda l=line: self.log_message(l, 'backend'))

                self.backend_process.wait()
                self.root.after(0, self.on_backend_stopped)

            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"启动失败: {e}", 'error'))

        thread = threading.Thread(target=run_backend, daemon=True)
        thread.start()

    def stop_backend(self):
        if not self.is_running:
            return

        try:
            self.backend_process.terminate()
            self.log_message("正在停止后端...", "info")
        except Exception as e:
            self.log_message(f"停止失败: {e}", 'error')

    def on_backend_started(self):
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.status_label.config(text="● 运行中", foreground="green")
        self.log_message("后端已启动", "success")
        self.update_status()

    def on_backend_stopped(self):
        self.is_running = False
        self.backend_process = None
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.status_label.config(text="● 未连接", foreground="red")
        self.log_message("后端已停止", "info")
        self.update_status()

    def test_connection(self):
        self.log_message("正在测试连接...", "info")

        try:
            response = requests.get("http://127.0.0.1:8000/", timeout=5)
            if response.status_code == 200:
                self.log_message("连接成功！后端正常响应", "success")
                messagebox.showinfo("测试结果", "✅ 连接成功！")
            else:
                self.log_message(f"连接失败: HTTP {response.status_code}", "error")
                messagebox.showerror("测试结果", f"❌ 连接失败: HTTP {response.status_code}")
        except requests.exceptions.ConnectionError:
            self.log_message("无法连接到后端，请确认后端已启动", "error")
            messagebox.showerror("测试结果", "❌ 无法连接到后端\n请确认后端已启动")
        except Exception as e:
            self.log_message(f"连接错误: {e}", "error")
            messagebox.showerror("测试结果", f"❌ 连接错误: {e}")

    # === 端口管理 ===
    def check_port(self):
        try:
            result = subprocess.run(
                ['netstat', '-ano', '|', 'findstr', ':8000'],
                capture_output=True,
                text=True,
                shell=True
            )

            if result.stdout:
                lines = result.stdout.strip().split('\n')
                listening_lines = [l for l in lines if 'LISTENING' in l]

                if listening_lines:
                    self.port_status.config(text=f"占用 ({len(listening_lines)} 个进程)", foreground="orange")
                    self.log_message(f"端口 8000 被占用:\n{result.stdout}", 'info')
                else:
                    self.port_status.config(text="空闲", foreground="green")
                    self.log_message("端口 8000 空闲", "success")
            else:
                self.port_status.config(text="空闲", foreground="green")
                self.log_message("端口 8000 空闲", "success")

        except Exception as e:
            self.port_status.config(text="检查失败", foreground="red")
            self.log_message(f"检查端口失败: {e}", 'error')

    def clear_port(self):
        self.log_message("正在清理端口 8000...", "info")

        try:
            # 查找占用端口的进程
            result = subprocess.run(
                'netstat -ano | findstr :8000',
                capture_output=True,
                text=True,
                shell=True
            )

            pids = set()
            for line in result.stdout.split('\n'):
                if 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        pids.add(pid)

            if not pids:
                self.log_message("没有发现占用端口的进程", "info")
                messagebox.showinfo("清理结果", "端口 8000 未被占用")
                return

            # 终止进程
            killed = []
            for pid in pids:
                try:
                    subprocess.run(['taskkill', '/F', '/PID', pid],
                                    capture_output=True, check=True)
                    killed.append(pid)
                except:
                    pass

            if killed:
                self.log_message(f"已终止进程: {', '.join(killed)}", "success")
                messagebox.showinfo("清理结果", f"✅ 已终止 {len(killed)} 个进程")
                self.port_status.config(text="已清理", foreground="green")
            else:
                self.log_message("未能终止任何进程", "error")
                messagebox.showwarning("清理结果", "未能终止进程")

        except Exception as e:
            self.log_message(f"清理端口失败: {e}", 'error')
            messagebox.showerror("清理结果", f"❌ 清理失败: {e}")

    # === 模型配置 ===
    def on_model_change(self):
        model_type = "Azure OpenAI" if self.model_var.get() == "true" else "本地 Ollama"
        self.log_message(f"切换到: {model_type}", "info")
        self.update_config_display()

    def save_model_config(self):
        try:
            # 读取当前 .env
            env_path = Path('.env')

            if not env_path.exists():
                messagebox.showerror("错误", ".env 文件不存在")
                return

            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 更新 USE_AZURE
            updated = []
            for line in lines:
                if line.startswith('USE_AZURE='):
                    updated.append(f'USE_AZURE={self.model_var.get()}\n')
                else:
                    updated.append(line)

            # 写回文件
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(updated)

            self.log_message("配置已保存，重启后端生效", "success")
            messagebox.showinfo("保存成功", "✅ 配置已保存\n请重启后端使配置生效")
            self.update_config_display()

        except Exception as e:
            self.log_message(f"保存配置失败: {e}", 'error')
            messagebox.showerror("保存失败", f"❌ 保存配置失败: {e}")

    def update_config_display(self):
        """更新配置显示"""
        load_dotenv()

        use_azure = os.getenv('USE_AZURE', 'false')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '未设置')
        ollama_base = os.getenv('OLLAMA_API_BASE', '未设置')

        self.config_text.delete('1.0', 'end')

        if use_azure == 'true':
            config = f"""模型: Azure OpenAI
端点: {endpoint}
版本: {os.getenv('AZURE_OPENAI_API_VERSION', '未设置')}
状态: {'已配置' if endpoint != '未设置' else '未配置'}"""
        else:
            config = f"""模型: 本地 Ollama
端点: {ollama_base}
状态: {'已配置' if ollama_base != '未设置' else '未配置'}"""

        self.config_text.insert('1.0', config)

    # === 文档浏览 ===
    def load_documents(self):
        """加载文档列表"""
        docs = [
            ("README.md", "项目主文档"),
            ("README_ARCHITECTURE.md", "项目逻辑架构"),
            ("README_GAME_OVERVIEW.md", "整体架构说明"),
            ("FOLDER_STRUCTURE.md", "文件夹结构"),
            ("MAIN_ARCHITECTURE.md", "Main.py 架构详解"),
        ]

        self.documents = {}
        for filename, title in docs:
            if Path(filename).exists():
                self.documents[title] = filename
                self.doc_listbox.insert('end', title)

    def on_doc_select(self, event):
        """文档选择事件"""
        selection = self.doc_listbox.curselection()
        if not selection:
            return

        title = self.doc_listbox.get(selection[0])
        filename = self.documents.get(title)

        if filename and Path(filename).exists():
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()

                self.doc_content.delete('1.0', 'end')
                self.doc_content.insert('1.0', content)
                self.log_message(f"已加载: {filename}", "info")

            except Exception as e:
                self.log_message(f"加载文档失败: {e}", 'error')

    def open_in_browser(self):
        """在浏览器中打开文档"""
        selection = self.doc_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个文档")
            return

        title = self.doc_listbox.get(selection[0])
        filename = self.documents.get(title)

        if filename and Path(filename).exists():
            try:
                file_path = Path(filename).resolve()
                webbrowser.open(f"file:///{file_path}")
                self.log_message(f"已在浏览器中打开: {filename}", "success")
            except Exception as e:
                self.log_message(f"打开失败: {e}", 'error')

    # === 通用功能 ===
    def log_message(self, message, level='info'):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")

        # 根据级别设置颜色标签
        tags = {
            'info': '[INFO]',
            'success': '[OK]',
            'error': '[ERROR]',
            'backend': '[BACKEND]'
        }

        tag = tags.get(level, '[LOG]')
        log_line = f"{timestamp} {tag} {message}\n"

        self.log_text.insert('end', log_line)
        self.log_text.see('end')

    def update_status(self):
        """更新状态"""
        if self.is_running:
            self.status_label.config(text="● 运行中", foreground="green")
        else:
            self.status_label.config(text="● 未连接", foreground="red")

def main():
    root = tk.Tk()
    app = BackendManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
