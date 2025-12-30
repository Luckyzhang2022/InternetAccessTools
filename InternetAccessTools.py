import sys
import os
import winreg
import requests
import shutil
import time
import re
from packaging import version
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,      # ← 新增
    QPushButton,     # ← 新增
    QMessageBox
)
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl

# === 配置区 ===
CURRENT_VERSION = "v0.0.0"
GITHUB_REPO = "Luckyzhang2022/InternetAccessTools"
DOWNLOAD_URL_TXT = "https://raw.githubusercontent.com/Luckyzhang2022/InternetAccessTools/main/downloadurl.txt"


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                  ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
}


# === 工具函数 ===
def get_proxy_settings():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if proxy_enable == 1:
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            winreg.CloseKey(key)
            return proxy_server or None
        else:
            winreg.CloseKey(key)
            return None
    except Exception:
        return None

def get():
    proxy_settings = get_proxy_settings()
    print("Proxy Settings:", proxy_settings)
    if proxy_settings:
        os.environ['HTTP_PROXY'] = proxy_settings
        os.environ['HTTPS_PROXY'] = proxy_settings

def del_algorithm():
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

# === 更新检查线程 ===
class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)  # (version, download_url)
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            # Step 1: 获取最新 Release 版本号
            release_api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            resp = requests.get(release_api, timeout=10)
            if resp.status_code != 200:
                # self.error_occurred.emit("无法连接 GitHub 获取版本信息")  # 屏蔽弹窗提示
                print('无法连接 GitHub 获取版本信息')
                return

            data = resp.json()
            latest_tag = data.get("tag_name", "").strip()
            fallback_url = data.get("html_url", "")

            if not latest_tag:
                self.error_occurred.emit("未获取到有效版本标签")
                return

            current_clean = CURRENT_VERSION.lstrip('v')
            latest_clean = latest_tag.lstrip('v')

            if version.parse(latest_clean) <= version.parse(current_clean):
                self.no_update.emit()
                return

            # Step 2: 从 downloadurl.txt 获取自定义下载地址
            custom_url = None
            raw_resp = requests.get(DOWNLOAD_URL_TXT, headers=headers, timeout=1000)
            print(raw_resp.text)
            if raw_resp.status_code == 200:
                content = raw_resp.text.strip()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and line.startswith(("http://", "https://")):
                        custom_url = line
                        print(custom_url)
                        break

            final_download_url = custom_url or fallback_url
            self.update_available.emit(latest_tag, final_download_url)

        except Exception as e:
            print(f"更新检查失败:\n{str(e)}")
            # self.error_occurred.emit(f"更新检查失败:\n{str(e)}")  注释掉更新失败的弹窗信息



# === 主窗口类 ===
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("上网小工具")
        self.setFixedSize(350, 150)  # 稍微调高以容纳按钮

        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignCenter)

        # === 上方：状态标签 ===
        self.label1 = QLabel("✅ 程序已启动")
        self.label1.setAlignment(Qt.AlignCenter)
        self.label1.setWordWrap(True)

        proxy = get_proxy_settings()
        self.label2 = QLabel(proxy or "⚠️ 未检测到系统代理")
        self.label2.setAlignment(Qt.AlignCenter)
        self.label2.setWordWrap(True)

        main_layout.addWidget(self.label1)
        main_layout.addWidget(self.label2)

        # === 中间：三个按钮 ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_reset = QPushButton("重置")
        self.btn_extend = QPushButton("增加时长")
        self.btn_disable = QPushButton("关闭全局")

        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_extend.clicked.connect(self.on_extend)
        self.btn_disable.clicked.connect(self.on_disable_global)

        button_layout.addWidget(self.btn_reset)
        button_layout.addWidget(self.btn_extend)
        button_layout.addWidget(self.btn_disable)

        # 将按钮布局放入一个容器并居中
        button_container = QWidget()
        button_container.setLayout(button_layout)
        button_container.setFixedWidth(320)  # 控制宽度避免拉伸

        main_layout.addWidget(button_container)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # 托盘 & 其他初始化
        self.tray_icon = QSystemTrayIcon(self)
        if self.tray_icon.isSystemTrayAvailable():
            self.setup_tray()
        else:
            self.tray_icon = None

        get()  # 应用代理
        QTimer.singleShot(2000, self.check_for_update)

    def on_reset(self):
        # 清除所有设置，恢复初始状态
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        self.label2.setText("🔄 已重置代理设置")

    # ===== 按钮对应的函数（即你所说的 A/B/C）=====
    def on_reset(self):
        """函数 A：重置"""
        try:
            import psutil
        except ImportError:
            print("错误：未找到psutil库。请使用pip安装：pip install psutil")
            exit(1)
        print("调用函数进行 重置操作")

        process_name = "GreenHub.exe"  # 请确认实际进程名称
        folder_path = os.path.join(os.environ['APPDATA'], 'GreenHub')


        # 查找目标进程
        target_procs = []
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if proc.info['name'].lower() == process_name.lower():
                target_procs.append(proc)


        # 处理存在的进程
        if target_procs:
            # 终止进程
            for proc in target_procs:
                try:
                    proc.terminate()
                except psutil.NoSuchProcess:
                    pass

            # 等待并强制终止未退出的进程
            gone, alive = psutil.wait_procs(target_procs, timeout=3)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            print(f"已关闭{process_name}进程")
            time.sleep(1)  # 确保进程完全释放资源
            QMessageBox.information(self, "操作", "已执行【重置】")

        # 无论进程是否存在都执行删除
        try:
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
                print(f"成功删除文件夹：{folder_path}")
            else:
                print(f"文件夹不存在：{folder_path}")
        except PermissionError:
            print("权限不足，请以管理员身份运行")
        except Exception as e:
            print(f"删除文件夹时出错：{str(e)}")


    def on_extend(self):
        """函数 B：增加时长"""
        print("调用函数 B: 增加时长")
        # TODO: 替换为你的真实逻辑
        def replace_text_in_file(file_path, pattern, repl):
            # 读取原始文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # 使用正则表达式替换内容
            new_content = re.sub(pattern, repl, content)

            # 如果内容有变动，则写入新文件并替换原文件
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(new_content)

        def modify_txt_files(directory, pattern, repl):
            # 遍历目录下的所有文件
            for filename in os.listdir(directory):
                if filename.startswith('config.json'):  # 检查文件startswith前缀(endswith后缀)是否为config.json
                    file_path = os.path.join(directory, filename)
                    replace_text_in_file(file_path, pattern, repl)
                    print(filename, '处理成功!')

        home_path = os.path.expanduser('~')    # 当前用户的目录路径

        # 使用示例
        directory_path = home_path + r'\AppData\Roaming\GreenHub'  # 指定目录路径
        pattern = '"minutes": '  # 要替换的旧文本
        repl = '"minutes": 98765'  # 新文本
        modify_txt_files(directory_path, pattern, repl)
        QMessageBox.information(self, "操作", "已执行【增加时长】")

    def on_disable_global(self):
        """函数 C：关闭全局代理"""
        print("调用函数 C: 关闭全局")
        # 示例：清除环境变量 + 提示
        del_algorithm()
        self.label2.setText("❌ 全局代理已关闭")
        QMessageBox.information(self, "操作", "全局代理已关闭")

    # ===== 以下保持不变（托盘、更新等）=====
    def setup_tray(self):

            # def setup_tray(self):
        menu = QMenu()

        # 主要操作（新增）
        reset_action = QAction("重置", self)
        extend_action = QAction("增加时长", self)
        disable_action = QAction("关闭全局", self)

        # 其他功能
        show_action = QAction("显示", self)
        update_action = QAction("检查更新", self)
        quit_action = QAction("退出", self)

        # 连接信号
        reset_action.triggered.connect(self.on_reset)
        extend_action.triggered.connect(self.on_extend)
        disable_action.triggered.connect(self.on_disable_global)
        show_action.triggered.connect(self.show_window)
        update_action.triggered.connect(self.check_for_update)
        quit_action.triggered.connect(self.quit_app)

        # 添加到菜单（建议分组）
        menu.addAction(reset_action)
        menu.addAction(extend_action)
        menu.addAction(disable_action)
        menu.addSeparator()  # 分隔线
        menu.addAction(show_action)
        menu.addAction(update_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

        # 设置图标
        if self.tray_icon.icon().isNull():
            self.tray_icon.setIcon(QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon))
        self.tray_icon.show()



    def check_for_update(self):
        if getattr(self, '_checking', False):
            return
        self._checking = True
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self.on_update_found)
        self.updater.no_update.connect(self.on_no_update)
        self.updater.error_occurred.connect(self.on_update_error)
        self.updater.finished.connect(lambda: setattr(self, '_checking', False))
        self.updater.start()

    def on_update_found(self, new_version, download_url):
        reply = QMessageBox.information(
            None, "发现新版本",
            f"当前版本：{CURRENT_VERSION}\n最新版本：{new_version}\n\n是否前往下载？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(download_url))

    def on_no_update(self):
        QMessageBox.information(None, "检查更新", "当前已是最新版本！")

    def on_update_error(self, msg):
        QMessageBox.warning(None, "更新检查", msg)

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def quit_app(self):
        del_algorithm()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "后台运行中",
                "程序已在系统托盘中继续运行。",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            del_algorithm()
            event.accept()

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange:
            if self.isMinimized() and self.tray_icon and self.tray_icon.isVisible():
                self.hide()
        super().changeEvent(event)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()
# === 主程序入口 ===
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
